import json
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.llm.providers import MockProvider, ModelReply
from app.models.entities import MemoryFact, ModelUsage, Reminder
from app.schemas.tasks import TaskCandidate
from app.services import model_chat
from app.tasks import repository as task_repository
from app.tasks.intent import grounded
from app.tasks.time_parse import clock_value, parse_target, time_parts


@pytest.mark.parametrize(
    "clock,period,expected",
    [
        ("十点", "上午", (10, 0)),
        ("十点半", "下午", (22, 30)),
        ("三点零五分", "下午", (15, 5)),
        ("10:05", "", (10, 5)),
        ("23点", "", (23, 0)),
        ("十二点", "凌晨", (0, 0)),
        ("十点", "", None),
        ("十二点", "晚上", None),
        ("十二点", "上午", None),
        ("十点", "白天", None),
        ("25:00", "", None),
        ("10:70", "", None),
        ("0点", "下午", None),
        ("十三点", "上午", None),
    ],
)
def test_clock_never_guesses_a_missing_or_contradictory_period(clock, period, expected):
    assert clock_value(clock, period) == expected


def test_relative_date_is_anchored_to_the_source_across_midnight_and_year_end():
    before_midnight = datetime(2026, 10, 26, 15, 59)
    assert parse_target("明天", "十点", "上午", before_midnight) == datetime(2026, 10, 27, 2)
    assert parse_target("明天", "十点", "上午", before_midnight + timedelta(minutes=2)) == datetime(
        2026, 10, 28, 2
    )
    assert parse_target("明天", "十点", "上午", datetime(2026, 12, 31, 15)) == datetime(
        2027, 1, 1, 2
    )
    assert parse_target("2026年2月30日", "10:00", "", before_midnight) is None
    assert parse_target("0001-01-01", "10:00", "", before_midnight) is None
    assert time_parts("明天上午十点去朋友家") == ("明天", "十点", "上午")


def test_model_guesses_become_missing_fields_and_hypothetical_tasks_are_rejected():
    source = "明天上午十点去朋友家，记得提醒我"
    candidate = TaskCandidate(
        source_excerpt=source,
        origin="我家",
        destination="朋友家",
        date_text="明天",
        clock_text="十点",
        period_text="上午",
        transport="taxi",
        time_semantics="arrival",
    )
    result = grounded(candidate, source)
    assert (
        result.origin == "" and result.transport == "unknown" and result.time_semantics == "unknown"
    )
    assert result.destination == "朋友家"
    assert grounded(candidate, "如果" + source) is None
    assert grounded(candidate.model_copy(update={"source_excerpt": "编造的安排"}), source) is None


@pytest.mark.parametrize("text", ["我不开车", "打车还是坐公交？"])
def test_negated_or_undecided_transport_is_never_a_confirmed_mode(text):
    assert (
        grounded(TaskCandidate(source_excerpt=text, transport="driving"), text).transport
        == "unknown"
    )
    assert (
        grounded(TaskCandidate(source_excerpt=text, transport="taxi"), text).transport == "unknown"
    )


def test_transport_evidence_must_belong_to_this_arrangement_not_another_clause():
    source = "明天去张阿姨家；后天打车去博物馆"
    item = TaskCandidate(source_excerpt="明天去张阿姨家", transport="taxi")
    assert grounded(item, source).transport == "unknown"


def test_explicit_trip_is_not_silently_downgraded_to_a_plain_timer():
    source = "明天十点去朋友家，提醒我"
    item = grounded(
        TaskCandidate(
            source_excerpt=source, kind="reminder", destination="朋友家", time_semantics="at"
        ),
        source,
    )
    assert item.kind == "outing" and item.time_semantics == "unknown"


def send(client, text, conversation=None, key=None):
    conversation = conversation or client.post("/api/v1/conversations").json()["id"]
    response = client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"content": text, "client_request_id": key or str(uuid.uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["assistant_message"]["status"] == "completed"
    return conversation, response.json()


def patch_fields(draft, **updates):
    return {
        "expected_revision": draft["revision"],
        "title": draft["title"],
        "time_text": "明天上午十一点",
        "time_semantics": "arrival",
        "origin": "合成出发地",
        "destination": "合成目的地",
        "transport": "taxi",
        "lead_minutes": 30,
        **updates,
    }


def test_trip_asks_only_missing_fields_persists_and_replays_without_another_call(
    clients, accounts, db
):
    a, _ = clients
    key = str(uuid.uuid4())
    text = "明天上午十点去张阿姨家做客，记得提醒我。"
    conversation, result = send(a, text, key=key)
    draft = result["assistant_message"]["task_drafts"][0]
    assert draft["status"] == "draft" and draft["scheduling_status"] == "not_scheduled"
    assert draft["time_semantics"] == "unknown" and draft["target_at"]
    assert draft["destination"] == "张阿姨家" and draft["origin"] == ""
    assert set(draft["missing_fields"]) == {"到达还是出发", "出发地", "交通方式"}
    assert "提醒尚未安排" in result["assistant_message"]["content"]
    assert a.get(f"/api/v1/conversations/{conversation}/messages").json()["items"][-1][
        "task_drafts"
    ] == [draft]
    _, repeated = send(a, text, conversation, key)
    assert repeated["replayed"] and repeated["assistant_message"]["task_drafts"] == [draft]
    assert (
        db.scalar(
            select(func.count())
            .select_from(ModelUsage)
            .where(ModelUsage.user_id == accounts[0][0].id)
        )
        == 1
    )
    assert (
        db.scalar(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == accounts[0][0].id)
        )
        == 0
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(MemoryFact)
            .where(MemoryFact.user_id == accounts[0][0].id)
        )
        == 0
    )


def test_followup_updates_same_draft_and_keeps_original_relative_date_and_evidence(clients):
    a, _ = clients
    conversation, first = send(a, "明天上午十点去张阿姨家做客，提醒我")
    original = first["assistant_message"]["task_drafts"][0]
    _, followup = send(a, "十点到，打车，从我家出发", conversation)
    draft = followup["assistant_message"]["task_drafts"][0]
    assert draft["id"] == original["id"] and draft["revision"] == original["revision"] + 1
    assert draft["target_at"] == original["target_at"] and draft["missing_fields"] == []
    assert (
        draft["time_semantics"] == "arrival"
        and draft["origin"] == "我家"
        and draft["transport"] == "taxi"
    )
    assert draft["source_message_id"] == first["user_message"]["id"]
    assert draft["last_message_id"] == followup["user_message"]["id"]
    assert draft["evidence"]["origin"]["message_id"] == followup["user_message"]["id"]
    history = a.get(f"/api/v1/conversations/{conversation}/messages").json()["items"]
    assert history[1]["task_drafts"] == [] and history[-1]["task_drafts"] == [draft]


def test_edit_confirm_defer_ownership_and_no_notification_job(clients, accounts, db):
    a, b = clients
    conversation, result = send(a, "明天上午十点去张阿姨家，提醒我")
    draft = result["assistant_message"]["task_drafts"][0]
    url = f"/api/v1/task-drafts/{draft['id']}"
    assert (
        a.post(url + "/actions", json={"expected_revision": 1, "action": "confirm"}).status_code
        == 422
    )
    assert b.get(url).status_code == 404
    assert b.get("/api/v1/task-drafts", params={"conversation_id": conversation}).status_code == 404
    assert b.post(url + "/edit", json=patch_fields(draft)).status_code == 404
    assert (
        b.post(url + "/actions", json={"expected_revision": 1, "action": "defer"}).status_code
        == 404
    )
    assert (
        a.post(
            url + "/edit", json={**patch_fields(draft), "user_id": accounts[1][0].id}
        ).status_code
        == 422
    )
    changed = a.post(url + "/edit", json=patch_fields(draft))
    assert changed.status_code == 200
    changed = changed.json()
    assert changed["evidence"]["clock_text"]["origin"] == "user_edit"
    assert changed["missing_fields"] == [] and changed["revision"] == 2
    assert a.post(url + "/edit", json=patch_fields(draft)).status_code == 409
    payload = {"expected_revision": 2, "action": "confirm"}
    confirmed = a.post(url + "/actions", json=payload).json()
    assert confirmed["status"] == "confirmed" and confirmed["confirmed_at"]
    assert a.post(url + "/actions", json=payload).json() == confirmed
    assert confirmed["scheduling_status"] == "not_scheduled"
    assert (
        db.scalar(
            select(func.count()).select_from(Reminder).where(Reminder.user_id == accounts[0][0].id)
        )
        == 0
    )
    reopened = a.post(url + "/edit", json=patch_fields(confirmed)).json()
    assert reopened["status"] == "draft" and reopened["confirmed_at"] is None
    postponed = a.post(
        url + "/actions", json={"expected_revision": reopened["revision"], "action": "defer"}
    ).json()
    assert postponed["status"] == "deferred"
    assert a.post(url + "/edit", json=patch_fields(postponed)).status_code == 409


def test_plain_reminder_and_multiple_arrangements_are_distinct_real_drafts(clients):
    a, _ = clients
    _, result = send(a, "明天上午九点提醒我浇花")
    draft = result["assistant_message"]["task_drafts"][0]
    assert draft["kind"] == "reminder" and draft["time_semantics"] == "at"
    assert draft["lead_minutes"] == 0 and draft["missing_fields"] == []
    _, result = send(a, "明天上午十点去张阿姨家，提醒我；后天下午三点去博物馆，提醒我")
    drafts = result["assistant_message"]["task_drafts"]
    assert len(drafts) == 2 and drafts[0]["id"] != drafts[1]["id"]
    assert drafts[0]["target_at"] != drafts[1]["target_at"]


@pytest.mark.parametrize(
    "text", ["如果明天上午十点去朋友家，提醒我，这只是假设", "不要提醒我明天出门", "你好"]
)
def test_not_an_explicit_task_creates_no_draft(clients, text):
    _, result = send(clients[0], text)
    assert result["assistant_message"]["task_drafts"] == []


def test_past_time_cannot_be_confirmed(clients):
    a, _ = clients
    _, result = send(a, "明天上午九点提醒我浇花")
    draft = result["assistant_message"]["task_drafts"][0]
    url = f"/api/v1/task-drafts/{draft['id']}"
    old = a.post(url + "/edit", json=patch_fields(draft, time_text="2000-01-01 10:00")).json()
    assert "尚未过去的时间" in old["missing_fields"]
    assert (
        a.post(
            url + "/actions", json={"expected_revision": old["revision"], "action": "confirm"}
        ).status_code
        == 422
    )


def test_task_prompt_reserves_the_complete_maximum_unicode_message(clients, monkeypatch):
    captured = []

    class Provider:
        def complete(self, prompts, *, json_output=False):
            assert json_output
            captured.extend(prompts)
            return ModelReply(
                json.dumps(
                    {"reply": "请补充事项", "memories": [], "memory_refs": [], "outings": []}
                ),
                "mock-v1",
                0,
                0,
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    source = "提醒我" + "🧓" * 1997
    send(clients[0], source)
    assert captured[-1]["content"] == source
    assert sum(len(m["content"].encode()) + 32 for m in captured) <= 12000


def test_chat_memory_and_task_share_one_provider_call(clients, accounts, db, monkeypatch):
    calls = []
    original = MockProvider.complete

    def counted(self, prompts, *, json_output=False):
        calls.append(json_output)
        return original(self, prompts, json_output=json_output)

    monkeypatch.setattr(MockProvider, "complete", counted)
    a, _ = clients
    assert a.post("/api/v1/memory-consent", json={"enabled": True}).status_code == 200
    _, result = send(a, "我的膝盖已经好了，明天上午十点去张阿姨家，提醒我")
    assert calls == [True] and len(result["assistant_message"]["task_drafts"]) == 1
    facts = list(db.scalars(select(MemoryFact).where(MemoryFact.user_id == accounts[0][0].id)))
    assert len(facts) == 1 and "膝盖已经好了" in facts[0].value and "明天" not in facts[0].value
    usage = db.scalar(select(ModelUsage).where(ModelUsage.user_id == accounts[0][0].id))
    assert usage.purpose == "chat_task" and usage.prompt_version == "chat-task/v2"


def test_task_real_provider_is_stopped_by_the_same_zero_daily_budget(clients, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("DEEPSEEK_DAILY_REQUEST_LIMIT", "0")
    get_settings.cache_clear()

    def forbidden(*args, **kwargs):
        raise AssertionError("No provider may be called after quota rejection")

    monkeypatch.setattr(model_chat, "get_provider", forbidden)
    a, _ = clients
    conversation = a.post("/api/v1/conversations").json()["id"]
    response = a.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"content": "明天上午十点去朋友家，提醒我", "client_request_id": str(uuid.uuid4())},
    ).json()
    assert response["assistant_message"]["error_code"] == "MODEL_BUDGET_EXCEEDED"
    assert response["assistant_message"]["task_drafts"] == []


def test_editing_clock_does_not_silently_roll_an_old_tomorrow_to_a_new_date(clients, monkeypatch):
    a, _ = clients
    _, result = send(a, "明天十点去张阿姨家，提醒我")
    draft = result["assistant_message"]["task_drafts"][0]
    original_reference = datetime.fromisoformat(
        draft["time_reference_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None)
    monkeypatch.setattr(task_repository, "utc_now", lambda: original_reference + timedelta(days=2))
    changed = a.post(f"/api/v1/task-drafts/{draft['id']}/edit", json=patch_fields(draft)).json()
    assert changed["resolved_date"] == draft["resolved_date"]
    assert changed["time_reference_at"] == draft["time_reference_at"]
    assert "尚未过去的时间" in changed["missing_fields"]


def test_remind_me_about_the_past_still_retrieves_memory_instead_of_creating_a_task(
    clients, accounts, db
):
    from tests.test_memory_retrieval import remember

    fact, _, original = remember(db, accounts[0][0], is_synthetic=True)
    _, result = send(clients[0], "提醒我上次膝盖受伤是什么时候？")
    reply = result["assistant_message"]
    assert reply["task_drafts"] == []
    assert any(ref["source_message_id"] == original.id for ref in reply["memory_refs"])
    assert (
        db.scalar(select(ModelUsage.purpose).where(ModelUsage.user_id == accounts[0][0].id))
        == "chat"
    )
