import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.llm.providers import DeepSeekProvider, ModelReply, ProviderFailure
from app.models.entities import Message, ModelBudget, ModelUsage
from app.services import model_chat


def settings(**values):
    return Settings(
        _env_file=None,
        llm_provider="deepseek",
        deepseek_api_key=SecretStr("synthetic-not-real"),
        **values,
    )


def send(client, text="合成模型验证"):
    conversation = client.post("/api/v1/conversations").json()["id"]
    url = f"/api/v1/conversations/{conversation}/messages"
    payload = {"content": text, "client_request_id": str(uuid.uuid4())}
    return url, payload, client.post(url, json=payload)


def test_official_request_has_output_cap_and_no_thinking_or_tools():
    calls = []

    def handle(request):
        calls.append(request)
        body = json.loads(request.content)
        assert body["max_tokens"] == 256 and body["thinking"] == {"type": "disabled"}
        assert "tools" not in body and body["stream"] is False
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"content": "合成回答"}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 3},
            },
        )

    result = DeepSeekProvider(settings(), httpx.MockTransport(handle)).complete(
        [{"role": "user", "content": "你好"}]
    )
    assert result == ModelReply("合成回答", "deepseek-flash", 20, 3)
    assert len(calls) == 1
    assert str(calls[0].url) == "https://api.deepseek.com/chat/completions"


@pytest.mark.parametrize("status", [401, 402, 429, 500, 302])
def test_provider_errors_do_not_retry_or_echo_body(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, text="SENSITIVE_RESPONSE_MUST_NOT_LEAK")

    with pytest.raises(ProviderFailure) as caught:
        DeepSeekProvider(settings(), httpx.MockTransport(handle)).complete([])
    assert caught.value.code == f"MODEL_HTTP_{status}"
    assert "SENSITIVE" not in str(caught.value)
    assert len(calls) == 1


def test_timeout_is_unknown_without_retry():
    calls = []

    def handle(request):
        calls.append(request)
        raise httpx.ReadTimeout("do not expose upstream details")

    with pytest.raises(ProviderFailure) as caught:
        DeepSeekProvider(settings(), httpx.MockTransport(handle)).complete([])
    assert caught.value.code == "MODEL_TIMEOUT_UNKNOWN" and len(calls) == 1


def test_invalid_response_is_unknown():
    provider = DeepSeekProvider(
        settings(), httpx.MockTransport(lambda r: httpx.Response(200, json={"choices": []}))
    )
    with pytest.raises(ProviderFailure) as caught:
        provider.complete([])
    assert caught.value.code == "MODEL_INVALID_RESPONSE_UNKNOWN"


def test_empty_response_is_distinct_and_keeps_usage_without_retry():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "model": "deepseek-flash",
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 3},
            },
        )

    with pytest.raises(ProviderFailure) as caught:
        DeepSeekProvider(settings(), httpx.MockTransport(handle)).complete([], json_output=True)
    assert caught.value.code == "MODEL_EMPTY_RESPONSE"
    assert caught.value.result.input_tokens == 20
    assert caught.value.result.output_tokens == 3 and len(calls) == 1


def test_arbitrary_endpoint_is_rejected():
    with pytest.raises(ValueError):
        settings(deepseek_base_url="https://untrusted.invalid")


def test_reserved_before_call_and_replay_never_bills_twice(clients, db, monkeypatch):
    config = settings()
    monkeypatch.setattr(model_chat, "get_settings", lambda: config)
    calls = []

    class Provider:
        def complete(self, prompts):
            calls.append(prompts)
            assert db.scalar(select(ModelUsage)).status == "reserved"
            assert db.scalar(select(Message).where(Message.role == "user")) is not None
            return ModelReply("合成 Provider 回复", "deepseek-flash", 10, 5)

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    a, _ = clients
    url, payload, response = send(a)
    assert response.json()["assistant_message"]["status"] == "completed"
    assert a.post(url, json=payload).json()["replayed"]
    assert len(calls) == 1
    usage = db.scalar(select(ModelUsage))
    assert usage.input_tokens == 10 and usage.output_tokens == 5
    assert usage.estimated_cost > 0 and usage.status == "completed"
    assert db.scalar(select(ModelBudget)).requests == 1


def test_timeout_persists_original_and_reserved_budget(clients, db, monkeypatch):
    monkeypatch.setattr(model_chat, "get_settings", lambda: settings())
    calls = []

    class Provider:
        def complete(self, prompts):
            calls.append(prompts)
            raise ProviderFailure("MODEL_TIMEOUT_UNKNOWN")

    monkeypatch.setattr(model_chat, "get_provider", lambda _: Provider())
    a, _ = clients
    url, payload, response = send(a)
    assert response.json()["assistant_message"]["error_code"] == "MODEL_TIMEOUT_UNKNOWN"
    assert a.post(url, json=payload).json()["replayed"]
    assert len(calls) == 1
    assert len(a.get(url).json()["items"]) == 2
    assert db.scalar(select(ModelUsage)).status == "unknown"
    assert db.scalar(select(ModelBudget)).reserved_tokens > 256


@pytest.mark.parametrize(
    "limits", [{"deepseek_daily_request_limit": 0}, {"deepseek_daily_token_limit": 1}]
)
def test_budget_blocks_before_provider_and_keeps_text(clients, db, monkeypatch, limits):
    monkeypatch.setattr(model_chat, "get_settings", lambda: settings(**limits))

    def forbidden(_):
        raise AssertionError("Budget must reject before provider construction")

    monkeypatch.setattr(model_chat, "get_provider", forbidden)
    _, _, response = send(clients[0])
    assert response.json()["assistant_message"]["error_code"] == "MODEL_BUDGET_EXCEEDED"
    assert db.scalar(select(ModelUsage)) is None


def test_operator_missing_key_then_safe_manual_retry(clients, db, monkeypatch):
    config = settings().model_copy(update={"deepseek_api_key": SecretStr("")})
    monkeypatch.setattr(model_chat, "get_settings", lambda: config)
    a, _ = clients
    url, payload, response = send(a)
    assert response.json()["assistant_message"]["error_code"] == "MODEL_NOT_CONFIGURED"
    assert db.scalar(select(ModelUsage)) is None
    config.llm_provider = "mock"
    response = a.post(url, json=payload).json()
    assert response["assistant_message"]["provider"] == "mock"
    assert response["assistant_message"]["status"] == "completed"
    assert len(a.get(url).json()["items"]) == 2


def test_budget_lock_enforces_global_limit_under_concurrency(mysql_engine):
    # Dedicated test schema, never the operator's development ledger.
    from datetime import datetime

    day = datetime.now(model_chat.ZoneInfo("Asia/Hong_Kong")).date().isoformat()
    with Session(mysql_engine) as db:
        assert db.scalar(select(ModelBudget).where(ModelBudget.day == day)) is None
    barrier = Barrier(2)

    def attempt():
        with Session(mysql_engine) as db:
            barrier.wait(timeout=5)
            try:
                model_chat.reserve_budget(db, settings(deepseek_daily_request_limit=1), 100)
                db.commit()
                return "reserved"
            except ProviderFailure:
                db.rollback()
                return "blocked"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        assert sorted(results) == ["blocked", "reserved"]
    finally:
        with Session(mysql_engine) as db:
            db.execute(delete(ModelBudget).where(ModelBudget.day == day))
            db.commit()


def test_context_has_hard_bounds_and_excludes_mock(clients, db):
    a, _ = clients
    url, _, _ = send(a, "合成长原文" * 200)
    for _ in range(8):
        a.post(url, json={"content": "继续合成消息" * 200, "client_request_id": str(uuid.uuid4())})
    latest = db.scalar(
        select(Message).where(Message.role == "user").order_by(Message.created_at.desc())
    )
    prompts = model_chat.context_messages(db, latest)
    assert len(prompts) <= 13
    assert sum(len(m["content"].encode()) + 32 for m in prompts) <= 12000
    assert not any("【Mock" in m["content"] for m in prompts)


def test_test_mode_never_inherits_live_key():
    assert get_settings().llm_provider == "mock"


def test_model_logs_only_metadata(clients, monkeypatch, caplog):
    monkeypatch.setattr(logging.getLogger("silver"), "propagate", True)
    with caplog.at_level(logging.INFO, logger="silver"):
        _, payload, response = send(clients[0], "PRIVATE_SYNTHETIC_CONTENT")
    assert response.status_code == 200
    assert payload["client_request_id"] in caplog.text
    assert "input_tokens=0" in caplog.text and "output_tokens=0" in caplog.text
    assert "PRIVATE_SYNTHETIC_CONTENT" not in caplog.text
    assert "synthetic-not-real" not in caplog.text
    for stage in (
        "context_ready",
        "request_persisted",
        "model_call_started",
        "model_call_returned",
        "reply_persisted",
    ):
        assert f"stage={stage}" in caplog.text
