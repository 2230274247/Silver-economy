import json

from tests.test_notifications import CLIENT_ID, configure_notifications, register
from tests.test_scheduling import confirm, preview, schedule_ready
from tests.test_task_drafts import send


def test_account_export_is_owner_scoped_private_and_has_download_headers(
    clients, accounts, db, monkeypatch
):
    configure_notifications(monkeypatch)
    a, b = clients
    a_id, b_id = accounts[0][0].id, accounts[1][0].id

    a_conversation, _ = send(a, "A 用户合成聊天原文")
    b_conversation, _ = send(b, "B 用户绝不能出现在 A 导出")
    assert a_conversation != b_conversation

    assert a.post("/api/v1/memory-consent", json={"enabled": True}).status_code == 200
    _ = send(a, "我上个月膝盖受伤了")
    draft = schedule_ready(a)
    previewed = preview(a, draft)
    assert previewed.status_code == 200
    task = confirm(a, previewed.json(), "a8ef2340-b8ad-49ac-bd2d-a6541b88a7c4")
    assert task.status_code == 201

    device = register(a, client_id=CLIENT_ID)
    assert device.status_code == 201
    assert register(b, client_id="synthetic-foreign-client").status_code == 201

    response = a.get(f"/api/v1/account/export?user_id={b_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith('attachment; filename="')
    assert response.headers["content-disposition"].endswith('.json"')
    payload = response.json()
    assert payload["schema_version"] == "silver-memory-export/v1"
    assert payload["account"]["login_name"] == accounts[0][0].login_name
    assert payload["account"]["memory_enabled"] is True

    serialized = response.text
    assert "A 用户合成聊天原文" in serialized
    assert "B 用户绝不能出现在 A 导出" not in serialized
    assert accounts[1][0].login_name not in serialized
    assert CLIENT_ID not in serialized
    assert "synthetic-foreign-client" not in serialized
    assert accounts[0][0].password_hash not in serialized
    assert "token_hash" not in serialized
    assert "push_client_id_ciphertext" not in serialized
    assert "fingerprint" not in serialized
    assert "raw_model_output" not in serialized
    assert "idempotency_key" not in serialized
    assert "lease_token" not in serialized

    data = payload["data"]
    conversation_ids = {item["id"] for item in data["conversations"]}
    assert a_conversation in conversation_ids
    assert b_conversation not in conversation_ids
    assert {item["id"] for item in data["task_drafts"]}
    assert data["outing_tasks"][0]["id"] == task.json()["id"]
    assert data["reminders"]
    assert data["notifications"]
    assert data["task_audit_logs"]
    assert data["memory_sources"]
    assert data["notification_devices"][0]["platform"] == "android"
    assert a_id != b_id


def test_export_requires_login_and_never_emits_foreign_rows(clients):
    a, b = clients
    send(a, "只属于 A 的导出隔离样本")
    send(b, "只属于 B 的导出隔离样本")
    exported = a.get("/api/v1/account/export")
    assert exported.status_code == 200
    contents = json.dumps(exported.json(), ensure_ascii=False)
    assert "只属于 A 的导出隔离样本" in contents
    assert "只属于 B 的导出隔离样本" not in contents
    assert a.cookies
    anonymous = a
    anonymous.cookies.clear()
    assert anonymous.get("/api/v1/account/export").status_code == 401
