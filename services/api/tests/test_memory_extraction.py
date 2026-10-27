import json
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.llm.providers import ModelReply
from app.memory.extractor import MemoryExtractor, event_time
from app.models.entities import MemoryFact, MemorySource, Message, User
from app.services import model_chat


def payload(source="上个月我膝盖受伤了", **fields):
    return {
        "kind": "health",
        "key": "膝盖",
        "value": source,
        "source_excerpt": source,
        "time_expression": "上个月",
        "state_text": "受伤",
        **fields,
    }


def parse(candidate, source="上个月我膝盖受伤了"):
    return MemoryExtractor().parse(
        json.dumps({"reply": "谢谢告诉我。", "memories": [candidate]}, ensure_ascii=False), source
    )


def send(client, content="上个月我膝盖受伤了", conversation=None):
    conversation = conversation or client.post("/api/v1/conversations").json()["id"]
    body = {"content": content, "client_request_id": str(uuid.uuid4())}
    url = f"/api/v1/conversations/{conversation}/messages"
    return url, body, client.post(url, json=body)


@pytest.mark.parametrize(
    "field,value",
    [
        ("key", "医院"),
        ("value", "确诊严重骨折"),
        ("time_expression", "2026年9月8日"),
        ("state_text", "严重"),
        ("source_excerpt", "我在某医院治疗过"),
    ],
)
def test_unstated_life_details_are_rejected(field, value):
    reply, items, rejected = parse(payload(**{field: value}))
    assert reply == "谢谢告诉我。" and items == [] and rejected == 1


@pytest.mark.parametrize(
    "source",
    [
        "如果我膝盖受伤了怎么办",
        "假如我膝盖受伤了",
        "编造我膝盖受伤了",
        "我没有受伤，只是在说膝盖",
        "不要记：我膝盖受伤了",
    ],
)
def test_hypothetical_negated_or_declined_not_saved(source):
    _, items, rejected = parse(payload(source, time_expression=""), source)
    assert items == [] and rejected == 1


@pytest.mark.parametrize(
    "expression,reference,expected,precision",
    [
        ("上个月", datetime(2026, 1, 1), (2025, 12, 1), "month"),
        ("上个月", datetime(2026, 1, 31, 20), (2026, 1, 1), "month"),
        ("2019年", datetime(2026, 10, 26), (2019, 1, 1), "year"),
        ("2019年5月", datetime(2026, 10, 26), (2019, 5, 1), "month"),
        ("2024年2月29日", datetime(2026, 10, 26), (2024, 2, 29), "day"),
    ],
)
def test_relative_calendar_anchor_keeps_precision(expression, reference, expected, precision):
    value, actual_precision = event_time(expression, reference)
    local = value.replace(tzinfo=UTC).astimezone(ZoneInfo("Asia/Hong_Kong"))
    assert (local.year, local.month, local.day) == expected and local.hour == 0
    assert actual_precision == precision


@pytest.mark.parametrize(
    "expression", ["多年前", "不记得了", "2023年2月29日", "0000年", "2019年15月"]
)
def test_unknown_or_invalid_time_does_not_invent_date(expression):
    assert event_time(expression, datetime(2026, 10, 26)) == (None, "unknown")


def test_default_no_consent_keeps_only_l0(clients, db):
    a, _ = clients
    assert a.get("/api/v1/memory-consent").json() == {"enabled": False}
    _, _, response = send(a)
    assert response.json()["user_message"]["memory_status"] == "disabled"
    assert db.scalar(select(func.count()).select_from(MemoryFact)) == 0


def test_capture_linked_raw_evidence_and_deduplicate(clients, db):
    a, _ = clients
    assert a.post("/api/v1/memory-consent", json={"enabled": True}).status_code == 200
    url, body, first = send(a)
    assert first.json()["user_message"]["memory_status"] == "captured"
    assert first.json()["assistant_message"]["content"].startswith("【Mock")
    assert a.post(url, json=body).json()["replayed"]
    # Same explicit statement in a different conversation adds a source, not a duplicate fact.
    send(a)
    facts = a.get("/api/v1/memories").json()["items"]
    assert len(facts) == 1 and facts[0]["status"] == "candidate"
    assert facts[0]["extractor_version"] == "chat-memory/v4+state-rule/v1"
    assert facts[0]["event_precision"] == "month" and facts[0]["confirmed_at"] is None
    sources = a.get(f"/api/v1/memories/{facts[0]['id']}/sources").json()["items"]
    assert len(sources) == 2 and all(s["source_excerpt"] == body["content"] for s in sources)
    assert sources[0]["message"]["content"] == body["content"]
    assert db.scalar(select(func.count()).select_from(MemorySource)) == 2
    raw = db.scalar(select(Message.raw_model_output).where(Message.role == "assistant").limit(1))
    assert json.loads(raw)["memories"][0]["value"] == body["content"]


def test_b_cannot_read_a_memories_sources_or_cursor(clients):
    a, b = clients
    a.post("/api/v1/memory-consent", json={"enabled": True})
    send(a)
    memory = a.get("/api/v1/memories").json()["items"][0]["id"]
    assert b.get("/api/v1/memories").json()["items"] == []
    assert b.get(f"/api/v1/memories/{memory}/sources").status_code == 404
    assert b.get("/api/v1/memories", params={"before_id": memory}).status_code == 404
    assert (
        b.post("/api/v1/memory-consent", json={"enabled": True, "user_id": "foreign"}).status_code
        == 422
    )


def test_withdrawal_during_model_call_prevents_capture(clients, db, monkeypatch):
    a, _ = clients
    a.post("/api/v1/memory-consent", json={"enabled": True})

    class Provider:
        def complete(self, prompts, *, json_output=False):
            assert json_output
            owner = db.scalar(select(User).where(User.memory_enabled.is_(True)))
            owner.memory_enabled = False
            db.commit()
            return ModelReply(
                json.dumps({"reply": "谢谢告诉我。", "memories": [payload()]}, ensure_ascii=False),
                "mock-v1",
                0,
                0,
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, response = send(a)
    assert response.json()["user_message"]["memory_status"] == "disabled"
    assert a.get("/api/v1/memories").json()["items"] == []


def test_broken_json_preserves_l0_without_auto_retry(clients, db, monkeypatch):
    a, _ = clients
    a.post("/api/v1/memory-consent", json={"enabled": True})
    calls = []

    class Provider:
        def complete(self, prompts, *, json_output=False):
            calls.append(prompts)
            return ModelReply('{"reply":"unfinished', "mock-v1", 0, 0)

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    url, body, response = send(a)
    result = response.json()
    assert result["user_message"]["content"] == body["content"]
    assert result["user_message"]["memory_status"] == "failed_schema"
    assert result["assistant_message"]["error_code"] == "MODEL_RESPONSE_FORMAT"
    a.post(url, json=body)
    assert len(calls) == 1 and a.get("/api/v1/memories").json()["items"] == []


def test_memory_and_source_pagination_preserves_every_record(clients):
    a, _ = clients
    a.post("/api/v1/memory-consent", json={"enabled": True})
    for text in ("上个月我膝盖受伤了", "上个月我膝盖受伤了", "我的膝盖好了"):
        send(a, text)
    first = a.get("/api/v1/memories", params={"limit": 1}).json()
    second = a.get(
        "/api/v1/memories", params={"limit": 1, "before_id": first["next_cursor"]}
    ).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    memory = next(item for item in [*first["items"], *second["items"]] if "受伤" in item["value"])
    url = f"/api/v1/memories/{memory['id']}/sources"
    source_one = a.get(url, params={"limit": 1}).json()
    source_two = a.get(url, params={"limit": 1, "before_id": source_one["next_cursor"]}).json()
    assert source_one["items"][0]["id"] != source_two["items"][0]["id"]
    assert source_two["next_cursor"] is None


def test_structured_provider_request_remains_one_capped_call():
    import httpx

    from app.llm.providers import DeepSeekProvider
    from tests.test_models import settings

    calls = []

    def handle(request):
        calls.append(request)
        body = json.loads(request.content)
        assert "response_format" not in body  # Avoid vendor JSON-mode empty replies.
        assert body["max_tokens"] == 256 and body["thinking"]["type"] == "disabled"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"reply":"谢谢","memories":[]}'}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 6},
            },
        )

    result = DeepSeekProvider(settings(), httpx.MockTransport(handle)).complete(
        [], json_output=True
    )
    assert len(calls) == 1 and result.output_tokens == 6


def test_mock_and_live_memory_views_do_not_mix(clients, accounts, db, monkeypatch):
    from app.api.v1 import memories
    from app.core.config import get_settings

    a, _ = clients
    a.post("/api/v1/memory-consent", json={"enabled": True})
    send(a)
    db.add(
        MemoryFact(
            user_id=accounts[0][0].id,
            kind="event",
            key="Synthetic",
            value="Synthetic live fixture",
            extractor_provider="deepseek",
            is_synthetic=True,
        )
    )
    db.flush()
    mock = a.get("/api/v1/memories").json()["items"]
    assert len(mock) == 1 and mock[0]["extractor_provider"] == "mock"
    config = get_settings().model_copy(update={"llm_provider": "deepseek"})
    monkeypatch.setattr(memories, "get_settings", lambda: config)
    live = a.get("/api/v1/memories").json()["items"]
    assert len(live) == 1 and live[0]["value"] == "Synthetic live fixture"


def test_partial_extraction_rejects_hallucination_without_losing_valid_fact():
    source = "上个月我膝盖受伤了"
    reply, items, rejected = MemoryExtractor().parse(
        json.dumps(
            {"reply": "谢谢告诉我。", "memories": [payload(), payload(value="严重骨折")]},
            ensure_ascii=False,
        ),
        source,
    )
    assert reply == "谢谢告诉我。" and len(items) == 1 and rejected == 1


def test_fact_span_preserves_negation_and_uncertainty_from_its_clause():
    source = "我的膝盖好像没有恢复"
    _, items, rejected = parse(
        payload(source, value="恢复", time_expression="", state_text="恢复"), source
    )
    assert rejected == 0 and items[0].value == source and items[0].source_excerpt == source


def test_question_mark_without_ma_does_not_create_a_fact():
    source = "我的膝盖恢复了？"
    _, items, rejected = parse(
        payload(source, value="恢复", time_expression="", state_text="恢复"), source
    )
    assert items == [] and rejected == 1
