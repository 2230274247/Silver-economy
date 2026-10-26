import uuid

import pytest


def test_persistent_messages_and_mock_reply_are_linked(clients):
    a, _ = clients
    conversation = a.post("/api/v1/conversations").json()["id"]
    payload = {"content": "合成测试：你好\n第二行", "client_request_id": str(uuid.uuid4())}
    response = a.post(f"/api/v1/conversations/{conversation}/messages", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["user_message"]["content"] == payload["content"]
    assert result["assistant_message"]["reply_to_message_id"] == result["user_message"]["id"]
    assert result["assistant_message"]["status"] == "completed"
    assert result["assistant_message"]["provider"] == "mock"
    assert result["assistant_message"]["content"].startswith("【Mock")
    history = a.get(f"/api/v1/conversations/{conversation}/messages").json()["items"]
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert history[0]["content"] == payload["content"]


def test_idempotency_does_not_duplicate_or_replace_text(clients):
    a, _ = clients
    conversation = a.post("/api/v1/conversations").json()["id"]
    url = f"/api/v1/conversations/{conversation}/messages"
    payload = {"content": "合成测试，幂等", "client_request_id": str(uuid.uuid4())}
    first = a.post(url, json=payload).json()
    repeated = a.post(url, json=payload).json()
    assert first["user_message"]["id"] == repeated["user_message"]["id"]
    assert repeated["replayed"]
    assert len(a.get(url).json()["items"]) == 2
    assert a.post(url, json={**payload, "content": "不同内容"}).status_code == 409


def test_b_cannot_read_or_send_to_a_conversation(clients):
    a, b = clients
    conversation = a.post("/api/v1/conversations").json()["id"]
    url = f"/api/v1/conversations/{conversation}/messages"
    assert b.get(url).status_code == 404
    assert (
        b.post(
            url, json={"content": "越权合成", "client_request_id": str(uuid.uuid4())}
        ).status_code
        == 404
    )
    assert all(
        item["id"] != conversation for item in b.get("/api/v1/conversations").json()["items"]
    )


def test_message_pagination_has_no_duplicates(clients):
    a, _ = clients
    conversation = a.post("/api/v1/conversations").json()["id"]
    url = f"/api/v1/conversations/{conversation}/messages"
    for i in range(4):
        assert (
            a.post(
                url, json={"content": f"合成分页 {i}", "client_request_id": str(uuid.uuid4())}
            ).status_code
            == 200
        )
    seen, cursor = [], None
    while True:
        result = a.get(url, params={"limit": 3, **({"before_id": cursor} if cursor else {})}).json()
        seen.extend(item["id"] for item in result["items"])
        cursor = result["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 8


@pytest.mark.parametrize("text", ["", "   ", "\n\n", "a" * 2001])
def test_invalid_message_is_rejected(clients, text):
    a, _ = clients
    conversation = a.post("/api/v1/conversations").json()["id"]
    url = f"/api/v1/conversations/{conversation}/messages"
    assert (
        a.post(url, json={"content": text, "client_request_id": str(uuid.uuid4())}).status_code
        == 422
    )
    assert a.get(url).json()["items"] == []
