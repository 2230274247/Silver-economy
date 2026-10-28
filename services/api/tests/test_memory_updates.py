import json
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.llm.providers import ModelReply
from app.memory.extractor import MemoryCandidate
from app.memory.repository import MemoryRepository
from app.memory.retriever import MemoryRetriever
from app.memory.updater import MemoryUpdater, health_state
from app.models.entities import MemoryRevision, MemorySource, ModelUsage
from app.services import model_chat
from tests.test_memory_retrieval import ask, remember
from tests.test_models import settings


def correct(client, fact, **changes):
    return client.post(
        f"/api/v1/memories/{fact.id}/correct",
        json={
            "expected_revision": fact.revision,
            "kind": fact.kind,
            "key": fact.key,
            "value": "我的膝盖已经好了",
            "time_expression": fact.time_expression or "",
            **changes,
        },
    )


def test_controls_revision_audit_original_and_budget(db, accounts, clients):
    fact, source, message = remember(db, accounts[0][0])
    client = clients[0]
    old_value, old_time = message.content, fact.event_at
    url = f"/api/v1/memories/{fact.id}"
    confirmed = client.post(url + "/confirm", json={"expected_revision": 1, "confirmed": True})
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"
    assert (
        client.post(url + "/confirm", json={"expected_revision": 1, "confirmed": False}).status_code
        == 409
    )
    assert correct(client, fact).status_code == 200
    assert fact.event_at == old_time  # '上个月' is not shifted to the edit month.
    assert message.content == old_value and source.source_excerpt == old_value
    assert fact.value_origin == "user_edit" and fact.revision == 3
    rows = client.get(url + "/revisions").json()["items"]
    assert [r["action"] for r in rows] == ["correct", "confirm"]
    assert rows[0]["before"]["value"] == old_value
    assert rows[0]["after"]["value"] == fact.value and rows[0]["actor"] == "user"
    denied = client.post(url + "/permission", json={"expected_revision": 3, "allowed": False})
    assert denied.status_code == 200
    assert MemoryRetriever().retrieve(db, fact.user_id, "膝盖") == []
    assert (
        client.post(url + "/permission", json={"expected_revision": 4, "allowed": True}).status_code
        == 200
    )
    assert client.post(url + "/invalidate", json={"expected_revision": 5}).status_code == 200
    assert MemoryRetriever().retrieve(db, fact.user_id, "膝盖") == []
    # Confirmation is not implicit reactivation of an invalid fact.
    assert (
        client.post(url + "/confirm", json={"expected_revision": 6, "confirmed": True}).json()[
            "status"
        ]
        == "inactive"
    )
    assert db.scalar(select(func.count()).select_from(ModelUsage)) == 0


def test_corrected_evidence_and_old_citation_are_distinguishable(db, accounts, clients):
    fact, _, message = remember(db, accounts[0][0])
    url, _, first = ask(clients[0])
    assert first.status_code == 200
    assert correct(clients[0], fact).status_code == 200
    old_ref = clients[0].get(url).json()["items"][-1]["memory_refs"][0]
    assert old_ref["changed_since_reply"] and old_ref["evidence_origin"] == "chat"
    _, _, answer = ask(clients[0], "我现在膝盖怎么样？")
    reference = answer.json()["assistant_message"]["memory_refs"][0]
    assert reference["evidence_text"] == fact.value
    assert reference["evidence_origin"] == "user_edit"
    assert reference["source_excerpt"] == message.content
    assert reference["memory_revision"] == 2 and not reference["changed_since_reply"]
    assert "已经好了" in answer.json()["assistant_message"]["content"]


def test_deleted_fact_is_gone_from_history_retrieval_search_and_source(db, accounts, clients):
    fact, _, original = remember(db, accounts[0][0])
    client = clients[0]
    url, payload, _ = ask(client)
    assert (
        client.request(
            "DELETE", f"/api/v1/memories/{fact.id}", json={"expected_revision": 1}
        ).status_code
        == 200
    )
    assert MemoryRetriever().retrieve(db, fact.user_id, "膝盖") == []
    assert client.get("/api/v1/memories/search?q=膝盖").json()["items"] == []
    assert client.get(f"/api/v1/memories/{fact.id}/sources").status_code == 404
    assert client.get(f"/api/v1/memories/{fact.id}/revisions").status_code == 404
    assert client.get(url).json()["items"][-1]["memory_refs"] == []
    assert client.post(url, json=payload).json()["assistant_message"]["memory_refs"] == []
    assert original.content == "上个月我膝盖受伤了"
    assert (
        db.scalar(select(MemoryRevision).where(MemoryRevision.memory_id == fact.id)).action
        == "delete"
    )
    assert "不知道" in ask(client, "我现在膝盖怎么样？")[2].json()["assistant_message"]["content"]


@pytest.mark.parametrize(
    "action,payload",
    [
        ("confirm", {"confirmed": True}),
        ("correct", {"kind": "health", "key": "膝盖", "value": "好了"}),
        ("permission", {"allowed": False}),
        ("invalidate", {}),
    ],
)
def test_other_user_cannot_mutate_or_read_audit(db, accounts, clients, action, payload):
    fact, _, _ = remember(db, accounts[0][0])
    base = f"/api/v1/memories/{fact.id}"
    assert (
        clients[1].post(base + "/" + action, json={"expected_revision": 1, **payload}).status_code
        == 404
    )
    assert clients[1].request("DELETE", base, json={"expected_revision": 1}).status_code == 404
    assert clients[1].get(base + "/revisions").status_code == 404
    assert fact.revision == 1


@pytest.mark.parametrize(
    "text",
    [
        "我膝盖没有恢复",
        "我膝盖可能好了",
        "朋友的膝盖好了",
        "我已经完全恢复了",
        "我的左膝盖好了吗？",
    ],
)
def test_uncertain_negated_or_ambiguous_claim_never_changes_state(text):
    assert health_state(text) is None


def test_explicit_recovery_preserves_injury_as_history_and_both_sources(db, accounts, clients):
    fact, _, original = remember(db, accounts[0][0])
    _, _, result = ask(clients[0], "我的膝盖已经好了")
    assert result.json()["user_message"]["memory_status"] == "captured"
    assert fact.fact_status == "historical" and fact.revision == 2
    current = MemoryRetriever().retrieve(db, fact.user_id, "我现在膝盖怎么样？")
    assert len(current) == 1 and current[0].fact.value == "我的膝盖已经好了"
    history = MemoryRetriever().retrieve(db, fact.user_id, "我之前膝盖发生过什么？")
    assert fact.id in {m.fact.id for m in history}
    assert original.content == "上个月我膝盖受伤了"
    assert (
        db.scalar(
            select(func.count())
            .select_from(MemorySource)
            .where(MemorySource.user_id == fact.user_id)
        )
        == 2
    )
    _, _, reply = ask(clients[0], "我现在膝盖怎么样？")
    assert "已经好了" in reply.json()["assistant_message"]["content"]
    assert "受伤" not in reply.json()["assistant_message"]["content"]


def test_correction_collision_and_invalid_input_do_not_change_any_record(db, accounts, clients):
    first, _, _ = remember(db, accounts[0][0])
    second, _, _ = remember(db, accounts[0][0], value="我的膝盖已经好了")
    assert correct(clients[0], second).status_code == 200
    assert correct(clients[0], first).status_code == 409
    db.refresh(first)
    assert first.revision == 1 and first.value == "上个月我膝盖受伤了"
    assert correct(clients[0], first, value="   ").status_code == 422
    assert correct(clients[0], first, value="x" * 1001).status_code == 422


def test_deleted_exact_fingerprint_cannot_be_recreated_from_original_source(db, accounts, clients):
    # Use repository-created fingerprint, not a fixture with a null fingerprint.
    _, _, message = remember(db, accounts[0][0], value="我的膝盖已经好了", expression="")
    candidate = MemoryCandidate(
        kind="health", key="膝盖", value=message.content, source_excerpt=message.content
    )
    stored = MemoryRepository().save_candidates(db, message, [candidate], "mock")[0]
    clients[0].request(
        "DELETE", f"/api/v1/memories/{stored.id}", json={"expected_revision": stored.revision}
    )
    assert MemoryRepository().save_candidates(db, message, [candidate], "mock") == []


def test_recovery_for_left_knee_does_not_invalidate_right_knee(db, accounts, clients):
    left, _, _ = remember(db, accounts[0][0], value="我的左膝盖受伤了")
    right, _, _ = remember(db, accounts[0][0], value="我的右膝盖受伤了")
    ask(clients[0], "我的左膝盖已经好了")
    assert left.fact_status == "historical" and right.fact_status == "active"


def test_time_expression_keeps_original_month_anchor_after_later_correction(db, accounts, clients):
    fact, _, _ = remember(db, accounts[0][0])
    fact.event_at = datetime(2020, 2, 29, 16)
    db.flush()
    assert correct(clients[0], fact).status_code == 200
    assert fact.event_at == datetime(2020, 2, 29, 16)
    assert json.loads(
        json.dumps(
            db.scalar(select(MemoryRevision).where(MemoryRevision.memory_id == fact.id)).after
        )
    )["event_at"].startswith("2020-02-29")


def test_empty_model_candidates_still_capture_explicit_recovery_without_second_call(
    db, accounts, clients, monkeypatch
):
    fact, _, _ = remember(db, accounts[0][0])

    class EmptyExtractor:
        calls = 0

        def complete(self, messages, **kwargs):
            self.calls += 1
            return ModelReply(
                json.dumps({"reply": "请确认这是哪次经历", "memories": [], "memory_refs": []}),
                "mock",
                0,
                0,
            )

    model = EmptyExtractor()
    monkeypatch.setattr(model_chat, "get_provider", lambda _: model)
    assert ask(clients[0], "我的膝盖已经好了")[2].status_code == 200
    assert fact.fact_status == "historical" and model.calls == 1
    current = MemoryRetriever().retrieve(db, fact.user_id, "我现在膝盖怎么样？")
    assert current[0].fact.value == "我的膝盖已经好了"


@pytest.mark.parametrize(
    "text",
    [
        "我已经完全恢复了",
        "我的膝盖没有恢复了",
        "我的膝盖好像好了",
        "如果我的膝盖好了",
        "我的膝盖应该好了",
        "朋友说我的膝盖好了",
        "我的膝盖好了？",
    ],
)
def test_deterministic_fallback_does_not_infer_unknown_or_uncertain_state(text):
    assert MemoryUpdater().complete_candidates(text, []) == []


def test_retelling_old_injury_does_not_replace_known_recovery(db, accounts, clients):
    recovered, _, _ = remember(db, accounts[0][0], value="我的膝盖已经好了", expression="")
    ask(clients[0], "上个月我的膝盖受伤了")
    current = MemoryRetriever().retrieve(db, recovered.user_id, "我现在膝盖怎么样？")
    assert [m.fact.id for m in current] == [recovered.id]
    assert recovered.fact_status == "active"


def test_uncertain_recovery_keeps_old_state_until_user_clarifies(db, accounts, clients):
    injury, _, _ = remember(db, accounts[0][0])
    ask(clients[0], "我的膝盖可能恢复了")
    assert injury.fact_status == "active" and injury.revision == 1


def test_rejected_paid_response_retains_actual_usage_and_estimated_cost(
    db, accounts, clients, monkeypatch
):
    remember(db, accounts[0][0], provider="deepseek")

    class Provider:
        def complete(self, *args, **kwargs):
            accounts[0][0].memory_enabled = False
            db.commit()
            return ModelReply(
                '{"reply":"private","memories":[],"memory_refs":["M1"]}', "deepseek-flash", 100, 10
            )

    monkeypatch.setattr(model_chat, "get_settings", lambda: settings())
    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, result = ask(clients[0])
    assert result.json()["assistant_message"]["error_code"] == "MEMORY_CONSENT_CHANGED"
    usage = db.scalar(select(ModelUsage))
    assert usage.status == "completed_rejected" and usage.input_tokens == 100
    assert float(usage.estimated_cost) == 0.000042
