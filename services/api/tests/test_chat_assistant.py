import json
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.llm.providers import DeepSeekProvider, ModelReply
from app.models.entities import AdminModelBudget, ModelBudget, ModelUsage
from app.services import model_chat, weather_search
from tests.test_models import send


def test_admin_role_is_server_owned_and_has_separate_budget(clients, accounts, db, monkeypatch):
    a, b = clients
    assert a.get("/api/v1/admin/model-status").status_code == 403
    accounts[0][0].is_admin = True
    db.commit()
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("DEEPSEEK_DAILY_REQUEST_LIMIT", "0")
    monkeypatch.setenv("ADMIN_DAILY_REQUEST_LIMIT", "2")
    get_settings.cache_clear()

    class Provider:
        def complete(self, prompts, *, json_output=False):
            return ModelReply("管理员自然回复", "deepseek-flash", 30, 10)

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, response = send(a, "你好")
    assert response.json()["assistant_message"]["content"] == "管理员自然回复"
    assert db.scalar(select(func.count()).select_from(AdminModelBudget)) == 1
    assert db.scalar(select(func.count()).select_from(ModelBudget)) == 0
    _, _, response = send(b, "你好")
    assert response.json()["assistant_message"]["error_code"] == "MODEL_BUDGET_EXCEEDED"
    status = a.get("/api/v1/admin/model-status").json()
    assert status["requests_used"] == 1 and status["daily_request_limit"] == 2
    assert "key" not in json.dumps(status).lower()


def test_weather_uses_one_search_then_model_and_replay_does_not_repeat(clients, db, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-test-key")
    get_settings.cache_clear()
    searched = []
    prompts_seen = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, *, headers, json):
            assert url == "https://api.deepseek.com/v1/tools/search"
            searched.append(json)

            class Response:
                status_code = 200

                def json(self):
                    return {
                        "results": [
                            {
                                "title": "Synthetic天气来源",
                                "url": "https://example.com/weather",
                                "summary": "合成测试预报，不是真实天气",
                            }
                        ]
                    }

            return Response()

    class Provider:
        def complete(self, prompts, *, json_output=False):
            prompts_seen.extend(prompts)
            return ModelReply("我查到了网页参考，请核对预报日期。", "deepseek-flash", 50, 20)

    monkeypatch.setattr(weather_search.httpx, "Client", Client)
    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    a, b = clients
    url, payload, response = send(a, "今天义乌的天气怎么样呀？")
    result = response.json()
    assert result["assistant_message"]["search_context"]["city"] == "义乌"
    assert len(searched) == 1 and len(prompts_seen) >= 2
    assert "Synthetic天气来源" in prompts_seen[0]["content"]
    assert "PUBLIC_MODEL_CONTEXT_JSON" in prompts_seen[0]["content"]
    assert a.post(url, json=payload).json()["replayed"]
    assert len(searched) == 1
    assert b.get(url).status_code == 404
    owner_id = a.get("/api/v1/me").json()["id"]
    assert (
        db.scalar(
            select(func.count()).select_from(ModelUsage).where(ModelUsage.user_id == owner_id)
        )
        == 2
    )
    missing_url, _, missing = send(a, "明天天气怎么样")
    expected_day = missing.json()["assistant_message"]["search_context"]["date"]
    assert len(searched) == 1
    answered = a.post(
        missing_url, json={"content": "北京", "client_request_id": str(uuid.uuid4())}
    ).json()
    assert answered["assistant_message"]["search_context"]["city"] == "北京"
    assert answered["assistant_message"]["search_context"]["date"] == expected_day
    assert len(searched) == 2


def test_task_preserves_model_reply_and_meeting_is_a_real_unconfirmed_draft(clients, monkeypatch):
    class Provider:
        def complete(self, prompts, *, json_output=False):
            return ModelReply(
                json.dumps(
                    {
                        "reply": "好的，明天下午一点开会。你希望提前多久提醒？",
                        "memories": [],
                        "memory_refs": [],
                        "outings": [
                            {
                                "kind": "reminder",
                                "source_excerpt": "明天下午1点我要开个会",
                                "date_text": "明天",
                                "period_text": "下午",
                                "clock_text": "1点",
                                "time_semantics": "at",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                "mock-v1",
                0,
                0,
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, response = send(clients[0], "明天下午1点我要开个会")
    result = response.json()["assistant_message"]
    assert "你希望提前多久提醒" in result["content"]
    assert len(result["task_drafts"]) == 1
    assert result["task_drafts"][0]["scheduling_status"] == "not_scheduled"


def test_weather_without_a_city_asks_instead_of_searching():
    assert weather_search.weather_plan("今天天气怎么样")["status"] == "missing_location"
    assert weather_search.weather_plan("义乌明天天气怎么样")["city"] == "义乌"
    assert weather_search.weather_plan("你调用什么模型") is None


def test_bad_auxiliary_fields_keep_reply_and_valid_task(clients, monkeypatch):
    a = clients[0]
    a.post("/api/v1/memory-consent", json={"enabled": True})

    class Provider:
        def complete(self, prompts, *, json_output=False):
            return ModelReply(
                json.dumps(
                    {
                        "reply": "好的，请核对时间。",
                        "memories": None,
                        "memory_refs": [],
                        "outings": [
                            {"kind": "unsupported"},
                            {"kind": "reminder", "source_excerpt": "半小时后提醒我收样品"},
                        ],
                        "optional_model_metadata": "ignored",
                    }
                ),
                "mock-v1",
                0,
                0,
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, response = send(a, "半小时后提醒我收样品")
    result = response.json()
    reply = result["assistant_message"]
    assert reply["status"] == "completed" and "好的，请核对时间" in reply["content"]
    assert "尚未安排通知" in reply["content"]
    assert len(reply["task_drafts"]) == 1
    draft = reply["task_drafts"][0]
    from datetime import datetime, timedelta

    source_at = datetime.fromisoformat(result["user_message"]["created_at"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(draft["target_at"]) == source_at + timedelta(minutes=30)
    assert draft["lead_minutes"] == 0 and draft["missing_fields"] == []
    assert draft["scheduling_status"] == "not_scheduled"
    assert result["user_message"]["memory_status"] == "partial_rejected"


def test_failed_old_question_is_not_replayed_on_new_topic(clients, db, monkeypatch):
    from app.models.entities import Message

    a = clients[0]
    url, _, _ = send(a, "Synthetic旧问题")
    old = db.scalar(select(Message).where(Message.content == "Synthetic旧问题"))
    failed = db.scalar(select(Message).where(Message.reply_to_message_id == old.id))
    failed.status, failed.content = "failed", ""
    db.commit()
    captured = []

    class Provider:
        def complete(self, prompts, *, json_output=False):
            captured.extend(prompts)
            return ModelReply("咖啡很好。", "mock-v1", 0, 0)

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    response = a.post(
        url, json={"content": "Synthetic咖啡话题", "client_request_id": str(uuid.uuid4())}
    )
    assert response.json()["assistant_message"]["content"] == "咖啡很好。"
    assert captured[-1]["content"] == "Synthetic咖啡话题"
    assert not any(m["content"] == "Synthetic旧问题" for m in captured)


@pytest.mark.parametrize("scenario", ["ordinary", "memory", "weather", "task"])
def test_all_chat_paths_use_text_transport_and_persist_one_reply(clients, monkeypatch, scenario):
    a = clients[0]
    text = "Synthetic今天有个好消息，很开心"
    if scenario != "ordinary":
        a.post("/api/v1/memory-consent", json={"enabled": True})
    if scenario == "task":
        text = "半小时后提醒我收Synthetic样品"
    elif scenario == "weather":
        text = "今天北京天气怎么样"
        monkeypatch.setattr(
            model_chat,
            "search_weather",
            lambda *args: {
                "status": "available",
                "city": "北京",
                "date": "2026-10-27",
                "results": [],
            },
        )
    calls = []

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        assert "response_format" not in body
        assert body["thinking"] == {"type": "disabled"} and body["stream"] is False
        assert body["messages"][-1]["content"] == text
        content = "Synthetic自然回复"
        if scenario != "ordinary":
            data = {"reply": content, "memories": [], "memory_refs": []}
            if scenario == "task":
                data["outings"] = [{"kind": "reminder", "source_excerpt": text}]
            content = "```json\n" + json.dumps(data) + "\n```"
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 25},
            },
        )

    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr(
        model_chat,
        "get_provider",
        lambda settings: DeepSeekProvider(settings, httpx.MockTransport(handle)),
    )
    url, payload, response = send(a, text)
    reply = response.json()["assistant_message"]
    assert reply["status"] == "completed" and "Synthetic自然回复" in reply["content"]
    assert len(reply["task_drafts"]) == (1 if scenario == "task" else 0)
    assert a.post(url, json=payload).json()["replayed"] and len(calls) == 1
    assert a.get(url).json()["items"][-1]["content"] == reply["content"]
    assert clients[1].get(url).status_code == 404


@pytest.mark.parametrize("task", [False, True])
def test_plain_model_text_survives_auxiliary_format_failure(clients, db, monkeypatch, task):
    a = clients[0]
    a.post("/api/v1/memory-consent", json={"enabled": True})

    class Provider:
        def complete(self, prompts, *, json_output=False):
            return ModelReply("很高兴听到这个消息！", "mock-v1", 0, 0)

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    text = "明天上午十点提醒我检查Synthetic结果" if task else "Synthetic项目有进展，很开心"
    url, payload, response = send(a, text)
    result = response.json()
    reply = result["assistant_message"]
    assert reply["status"] == "completed" and reply["content"].startswith("很高兴听到这个消息！")
    assert result["user_message"]["memory_status"] == "failed_schema"
    assert reply["task_drafts"] == [] and reply["memory_refs"] == []
    if task:
        assert "尚未安排通知" in reply["content"]
    assert db.scalar(select(ModelUsage)).status == "completed_partial"
    assert a.post(url, json=payload).json()["replayed"]


@pytest.mark.parametrize("references", [None, {"ref": "M1"}, ["M1"], [{"ref": "M1"}]])
def test_bad_reference_shape_never_grants_access_or_discards_current_reply(
    clients, monkeypatch, references
):
    a = clients[0]
    a.post("/api/v1/memory-consent", json={"enabled": True})

    class Provider:
        def complete(self, prompts, *, json_output=False):
            return ModelReply(
                json.dumps(
                    {
                        "reply": "恭喜，合成项目测试成功，值得开心！",
                        "memories": [],
                        "memory_refs": references,
                    }
                ),
                "mock-v1",
                0,
                0,
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, response = send(a, "Synthetic合成项目测试成功，很开心")
    result = response.json()
    assert result["assistant_message"]["status"] == "completed"
    assert "值得开心" in result["assistant_message"]["content"]
    assert result["assistant_message"]["memory_refs"] == []
    assert result["user_message"]["memory_status"] == "partial_rejected"
