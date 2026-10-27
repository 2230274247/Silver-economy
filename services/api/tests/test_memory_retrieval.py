import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.llm.providers import ModelReply
from app.memory.context import CONTEXT_MARKER, ContextBuilder
from app.memory.extractor import event_time
from app.memory.retriever import MemoryRetriever
from app.models.entities import (
    Conversation,
    MemoryFact,
    MemorySource,
    MemoryUse,
    Message,
    ModelUsage,
)
from app.services import model_chat
from tests.test_auth import sign_in


def remember(
    db,
    user,
    *,
    kind="health",
    key="膝盖",
    value="上个月我膝盖受伤了",
    provider="mock",
    expression="上个月",
    **fields,
):
    user.memory_enabled = True
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    db.flush()
    message = Message(user_id=user.id, conversation_id=conversation.id, role="user", content=value)
    db.add(message)
    db.flush()
    when, precision = event_time(expression, message.created_at)
    fact = MemoryFact(
        user_id=user.id,
        kind=kind,
        key=key,
        value=value,
        fact_status="active",
        retrieval_allowed=True,
        extractor_provider=provider,
        event_at=when,
        event_precision=precision,
        time_expression=expression,
        **fields,
    )
    db.add(fact)
    db.flush()
    source = MemorySource(
        user_id=user.id, memory_id=fact.id, message_id=message.id, source_excerpt=value
    )
    db.add(source)
    db.flush()
    return fact, source, message


def ask(client, content="你还记得我膝盖受伤的事吗？"):
    conversation = client.post("/api/v1/conversations").json()["id"]
    url = f"/api/v1/conversations/{conversation}/messages"
    payload = {"content": content, "client_request_id": str(uuid.uuid4())}
    return url, payload, client.post(url, json=payload)


def test_exact_year_and_source_are_retrieved(db, accounts):
    fact, source, _ = remember(
        db,
        accounts[0][0],
        kind="travel",
        key="苏州",
        value="2019年我去过苏州旅游",
        expression="2019年",
    )
    found = MemoryRetriever().retrieve(db, accounts[0][0].id, "我是哪一年去苏州旅游的？")
    assert found[0].fact.id == fact.id and found[0].source.id == source.id
    context = ContextBuilder().build(model_chat.MEMORY_PROMPT, found, "我是哪一年去苏州旅游的？")
    data = json.loads(context.system_prompt.split(CONTEXT_MARKER)[1])
    assert data[0]["event_time"] == "2019年"  # UTC year anchor is not misread as 2018.
    assert data[0]["ref"] == "M1" and source.source_excerpt in data[0]["text"]


@pytest.mark.parametrize(
    "question",
    ["我曾经在哪座城市上过几年班？", "我以前上了三年班的是哪座城？", "我曾在哪座城市任职三年？"],
)
def test_semantic_work_paraphrase_without_shared_work_keyword(db, accounts, question):
    fact, _, _ = remember(
        db, accounts[0][0], kind="work", key="杭州", value="我以前在杭州工作过三年", expression=""
    )
    found = MemoryRetriever().retrieve(db, accounts[0][0].id, question)
    assert [item.fact.id for item in found] == [fact.id]


@pytest.mark.parametrize(
    "field,value",
    [
        ("deleted_at", datetime(2026, 1, 1)),
        ("fact_status", "inactive"),
        ("retrieval_allowed", False),
        ("valid_to", datetime(2020, 1, 1)),
        ("valid_from", datetime(2090, 1, 1)),
    ],
)
def test_disallowed_states_never_enter_context(db, accounts, field, value):
    fact, _, _ = remember(db, accounts[0][0])
    setattr(fact, field, value)
    db.flush()
    assert MemoryRetriever().retrieve(db, fact.user_id, "膝盖") == []


def test_user_and_provider_filters_apply_before_ranking(db, accounts):
    a, b = accounts[0][0], accounts[1][0]
    own, _, _ = remember(db, a)
    remember(db, b, value="只有B知道的膝盖经历")
    remember(db, a, value="Synthetic live 膝盖经历", provider="deepseek")
    found = MemoryRetriever().retrieve(db, a.id, "膝盖")
    assert [item.fact.id for item in found] == [own.id]
    live = MemoryRetriever().retrieve(db, a.id, "膝盖", provider="deepseek")
    assert len(live) == 1 and live[0].fact.extractor_provider == "deepseek"


def test_withdrawal_stops_ai_retrieval_but_not_explicit_library_search(db, accounts):
    user = accounts[0][0]
    fact, _, _ = remember(db, user)
    user.memory_enabled = False
    db.flush()
    assert MemoryRetriever().retrieve(db, user.id, "膝盖") == []
    assert MemoryRetriever().retrieve(db, user.id, "膝盖", for_context=False)[0].fact.id == fact.id


def test_untraceable_high_rank_record_does_not_displace_valid_source(db, accounts):
    user = accounts[0][0]
    fact, _, _ = remember(db, user, key="膝盖", value="膝盖相关的有来源陈述")
    db.add(
        MemoryFact(
            user_id=user.id,
            kind="health",
            key="膝盖",
            value="膝盖膝盖膝盖无来源",
            retrieval_allowed=True,
            fact_status="active",
            extractor_provider="mock",
        )
    )
    db.flush()
    assert MemoryRetriever().retrieve(db, user.id, "膝盖", limit=1)[0].fact.id == fact.id


def test_specific_unknown_meal_does_not_reuse_habits_or_unrelated_date(db, accounts):
    user = accounts[0][0]
    remember(db, user, kind="habit", key="早餐", value="我每天早餐吃粥", expression="")
    remember(db, user, kind="travel", key="苏州", value="2018年我去苏州旅游", expression="2018年")
    assert MemoryRetriever().retrieve(db, user.id, "我去年6月18日中午吃了什么？") == []


def test_named_travel_companion_is_required_before_ranking_common_destination(db, accounts):
    user = accounts[0][0]
    correct, _, _ = remember(
        db, user, kind="travel", key="秋云", value="2007年我和秋云去过丽江", expression="2007年"
    )
    for i in range(10):
        remember(
            db,
            user,
            kind="travel",
            key="丽江",
            value=f"2025年我第{i}次去丽江旅游，和建平游览古城",
            expression="2025年",
        )
    found = MemoryRetriever().retrieve(db, user.id, "翻旧事，秋云同行的丽江旅行是哪年？")
    assert [memory.fact.id for memory in found] == [correct.id]


def test_coworker_alone_does_not_establish_neighbor_relationship(db, accounts):
    user = accounts[0][0]
    remember(db, user, kind="relationship", key="宋安", value="我的同事宋安在广州任职")
    assert MemoryRetriever().retrieve(db, user.id, "哪位同事住在我隔壁？") == []


def test_context_selects_at_most_five_and_reserves_full_unicode_input(db, accounts):
    user = accounts[0][0]
    for i in range(8):
        remember(db, user, key="主题", value=f"Synthetic主题事实{i}，原文来源明确", expression="")
    found = MemoryRetriever().retrieve(db, user.id, "主题", limit=30)
    assert len(found) == 8
    text = "🧓" * 2000
    context = ContextBuilder().build(model_chat.MEMORY_PROMPT, found, text)
    assert len(context.selected) <= 5
    assert len(context.system_prompt.encode()) + len(text.encode()) + 64 <= 12000
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    db.flush()
    item = Message(user_id=user.id, conversation_id=conversation.id, role="user", content=text)
    db.add(item)
    db.flush()
    prompts = model_chat.context_messages(db, item, context.system_prompt)
    assert prompts[-1]["content"] == text
    assert sum(len(p["content"].encode()) + 32 for p in prompts) <= 12000


def test_relogin_new_conversation_reply_cites_source_and_replays_once(clients, db, accounts):
    a, _ = clients
    fact, source, original = remember(db, accounts[0][0])
    a.post("/api/v1/auth/logout")
    sign_in(a, accounts[0])
    url, payload, response = ask(a)
    result = response.json()
    assert result["assistant_message"]["status"] == "completed"
    refs = result["assistant_message"]["memory_refs"]
    assert len(refs) == 1 and refs[0]["memory_id"] == fact.id
    assert (
        refs[0]["source_message_id"] == original.id
        and refs[0]["source_excerpt"] == source.source_excerpt
    )
    assert "膝盖受伤" in result["assistant_message"]["content"]
    assert a.post(url, json=payload).json()["replayed"]
    assert db.scalar(select(func.count()).select_from(MemoryUse)) == 1
    assert (
        db.scalar(select(func.count()).select_from(MemoryFact)) == 1
    )  # The question is not re-imported as a new fact.
    history = a.get(url).json()["items"]
    assert history[-1]["memory_refs"] == refs


@pytest.mark.parametrize("reply_mode", ["labeled", "plain", "unknown_reference"])
@pytest.mark.parametrize("change", ["value", "deleted", "revoked"])
def test_changed_evidence_during_generation_blocks_stale_answer(
    clients, db, accounts, monkeypatch, change, reply_mode
):
    fact, _, _ = remember(db, accounts[0][0])

    class Provider:
        def complete(self, prompts, *, json_output=False):
            assert "膝盖受伤" in prompts[0]["content"]
            if change == "value":
                fact.value = "膝盖已经恢复"
            elif change == "deleted":
                fact.deleted_at = datetime.now(UTC).replace(tzinfo=None)
            else:
                accounts[0][0].memory_enabled = False
            db.commit()
            if reply_mode == "plain":
                return ModelReply("旧来源不应展示", "mock-v1", 0, 0)
            return ModelReply(
                json.dumps(
                    {
                        "reply": "旧来源不应展示",
                        "memories": [],
                        "memory_refs": ["M99" if reply_mode == "unknown_reference" else "M1"],
                    },
                    ensure_ascii=False,
                ),
                "mock-v1",
                0,
                0,
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    _, _, response = ask(clients[0])
    assistant = response.json()["assistant_message"]
    assert (
        assistant["status"] == "failed"
        and assistant["content"] == ""
        and assistant["memory_refs"] == []
    )
    assert assistant["error_code"] in {"MEMORY_CHANGED_DURING_REPLY", "MEMORY_CONSENT_CHANGED"}
    assert db.scalar(select(func.count()).select_from(MemoryUse)) == 0


def test_invented_reference_omitted_without_losing_reply_or_retry(
    clients, db, accounts, monkeypatch
):
    remember(db, accounts[0][0])
    calls = []

    class Provider:
        def complete(self, prompts, *, json_output=False):
            calls.append(1)
            return ModelReply(
                '{"reply":"自然回复","memories":[],"memory_refs":["M99"]}', "mock-v1", 0, 0
            )

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    url, payload, response = ask(clients[0])
    result = response.json()
    assert result["assistant_message"]["status"] == "completed"
    assert result["assistant_message"]["content"] == "自然回复"
    assert result["assistant_message"]["memory_refs"] == []
    assert result["user_message"]["memory_status"] == "partial_rejected"
    clients[0].post(url, json=payload)
    assert calls == [1] and db.scalar(select(ModelUsage)).status == "completed_partial"
    assert db.scalar(select(ModelUsage)).error_code == "MEMORY_REFERENCE_IGNORED"
    assert db.scalar(select(func.count()).select_from(MemoryUse)) == 0


def test_reference_fk_rejects_another_users_fact_and_false_source_membership(db, accounts):
    a, b = accounts[0][0], accounts[1][0]
    fact_a, _, original_a = remember(db, a)
    fact_b, _, original_b = remember(db, b)
    reply = Message(
        user_id=a.id,
        conversation_id=original_a.conversation_id,
        role="assistant",
        content="Synthetic",
    )
    db.add(reply)
    db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            MemoryUse(
                user_id=a.id,
                assistant_message_id=reply.id,
                memory_id=fact_b.id,
                source_message_id=original_b.id,
                reference_label="M1",
            )
        )
        db.flush()
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            MemoryUse(
                user_id=a.id,
                assistant_message_id=reply.id,
                memory_id=fact_a.id,
                source_message_id=original_b.id,
                reference_label="M1",
            )
        )
        db.flush()


def test_search_is_user_scoped_and_literal_wildcards_do_not_expand(clients, db, accounts):
    fact, _, _ = remember(db, accounts[0][0], kind="event", key="费率", value="Synthetic费率5%")
    remember(db, accounts[1][0], kind="event", key="费率", value="B的费率9%")
    response = clients[0].get("/api/v1/memories/search", params={"q": "%"})
    assert [item["id"] for item in response.json()["items"]] == [fact.id]
    assert clients[0].get("/api/v1/memories/search", params={"q": "_' OR 1=1--"}).status_code == 200


def test_unrelated_long_latin_query_is_not_split_into_accidental_bigrams(db, accounts):
    remember(db, accounts[0][0], value="Synthetic膝盖经历", key="膝盖")
    assert (
        MemoryRetriever().retrieve(db, accounts[0][0].id, "zzabsentmvpcutydzz", for_context=False)
        == []
    )


def test_no_evidence_reply_admits_unknown_without_sources(clients, db, accounts):
    remember(db, accounts[0][0], kind="habit", key="早餐", value="我每天早餐吃粥", expression="")
    _, _, response = ask(clients[0], "我去年6月18日中午吃了什么？")
    reply = response.json()["assistant_message"]
    assert reply["status"] == "completed" and "不知道" in reply["content"]
    assert reply["memory_refs"] == []
