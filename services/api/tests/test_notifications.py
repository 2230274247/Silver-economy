import json
from contextlib import nullcontext

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.main import app
from app.models.entities import NotificationDevice, NotificationJob
from app.notifications.providers import UniPushBridgeProvider
from app.notifications.worker import process_once
from tests.test_scheduling import make_due

CLIENT_ID = "synthetic-unipush-client-0001"
BRIDGE_TOKEN = "synthetic-bridge-token"


def configure_notifications(monkeypatch, provider="mock"):
    monkeypatch.setenv(
        "NOTIFICATION_DEVICE_ENCRYPTION_KEY",
        Fernet.generate_key().decode(),
    )
    monkeypatch.setenv("NOTIFICATIONS_PROVIDER", provider)
    monkeypatch.setenv("UNI_PUSH_BRIDGE_URL", "")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_TOKEN", "")
    get_settings.cache_clear()


def register(client, *, permission="granted", client_id=CLIENT_ID):
    return client.post(
        "/api/v1/notification-devices",
        json={
            "platform": "android",
            "push_client_id": client_id,
            "permission_status": permission,
            "app_version": "0.1.0-synthetic",
            "device_label": "Synthetic Android",
        },
    )


def test_device_registration_encrypts_reassigns_isolates_and_revokes(
    clients,
    db,
    monkeypatch,
):
    configure_notifications(monkeypatch)
    a, b = clients
    response = register(a)
    assert response.status_code == 201
    payload = response.json()
    assert payload["can_receive"] is True
    assert CLIENT_ID not in json.dumps(payload)

    device = db.scalar(select(NotificationDevice).where(NotificationDevice.id == payload["id"]))
    assert CLIENT_ID not in device.push_client_id_ciphertext
    assert len(device.fingerprint) == 64

    reassigned = register(b)
    assert reassigned.status_code == 201
    db.refresh(device)
    assert device.revoked_at is not None
    assert device.permission_status == "granted"

    denied = register(a, permission="denied", client_id="synthetic-denied-client")
    assert denied.status_code == 201
    assert denied.json()["can_receive"] is False

    denied_id = denied.json()["id"]
    assert b.delete(f"/api/v1/notification-devices/{denied_id}").status_code == 404
    revoked = a.delete(f"/api/v1/notification-devices/{denied_id}")
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert a.get("/api/v1/notification-devices").json()["items"][0]["platform"] == "android"


def test_bridge_receives_server_decrypted_device_and_never_sends_private_trip_text(
    clients,
    db,
    monkeypatch,
):
    configure_notifications(monkeypatch, provider="unipush_bridge")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_URL", "https://bridge.example.invalid/push")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_TOKEN", BRIDGE_TOKEN)
    get_settings.cache_clear()
    a, b = clients
    device = register(a).json()

    job, _ = make_due(db, a)
    captured = {}

    class Response:
        status_code = 202

        def json(self):
            return {"message_id": "synthetic-provider-message"}

    class Client:
        def post(self, url, *, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return Response()

    provider = UniPushBridgeProvider(get_settings(), Client())
    result = process_once(
        factory=lambda: nullcontext(db),
        provider=provider,
        owner="synthetic-bridge-worker",
    )
    assert result["submitted"] == 1
    assert job.status == "submitted_to_provider"
    assert job.provider == "unipush_bridge"
    assert job.channel == "android_device"
    assert job.device_id == device["id"]
    assert captured["json"]["client_id"] == CLIENT_ID
    assert captured["json"]["request_id"] == job.idempotency_key
    assert "我不该出现在通知" not in json.dumps(captured["json"], ensure_ascii=False)
    assert captured["headers"]["Authorization"] == f"Bearer {BRIDGE_TOKEN}"
    assert a.get("/api/v1/notifications").json()["items"][0]["is_mock"] is False
    assert b.get("/api/v1/notifications").json()["items"] == []


def test_bridge_without_active_device_fails_instead_of_faking_delivery(
    clients,
    db,
    monkeypatch,
):
    configure_notifications(monkeypatch, provider="unipush_bridge")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_URL", "https://bridge.example.invalid/push")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_TOKEN", BRIDGE_TOKEN)
    get_settings.cache_clear()
    a, _ = clients
    device = register(a, permission="denied").json()
    job, _ = make_due(db, a)

    class Client:
        def post(self, *args, **kwargs):
            raise AssertionError("Bridge must not be called without an active device")

    result = process_once(
        factory=lambda: nullcontext(db),
        provider=UniPushBridgeProvider(get_settings(), Client()),
        owner="synthetic-no-device-worker",
    )
    assert result["failed"] == 1
    assert job.status == "failed"
    assert job.error_code == "NO_ACTIVE_DEVICE"
    assert job.device_id is None
    assert job.provider_message_id is None
    assert db.get(NotificationDevice, device["id"]).permission_status == "denied"


def test_notification_status_distinguishes_configuration_from_real_delivery(monkeypatch):
    configure_notifications(monkeypatch, provider="mock")
    status = TestClient(app).get("/api/v1/notifications/status")
    assert status.status_code == 200
    assert status.json()["provider"] == "mock"
    assert status.json()["device_encryption_configured"] is True
    assert status.json()["physical_delivery_verified"] is False

    # Keep the ORM import exercised here so a schema/model mismatch fails early.
    assert NotificationDevice.__tablename__ == "notification_devices"
    assert NotificationJob.__tablename__ == "notification_jobs"


def test_bridge_timeout_never_blindly_retries_an_unknown_delivery(clients, db, monkeypatch):
    configure_notifications(monkeypatch, provider="unipush_bridge")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_URL", "https://bridge.example.invalid/push")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_TOKEN", BRIDGE_TOKEN)
    get_settings.cache_clear()
    a, _ = clients
    register(a)
    job, _ = make_due(db, a)

    class Client:
        def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("Synthetic provider outcome unknown")

    result = process_once(
        factory=lambda: nullcontext(db),
        provider=UniPushBridgeProvider(get_settings(), Client()),
    )
    assert result["unknown"] == 1
    assert job.status == "unknown"
    assert process_once(factory=lambda: nullcontext(db))["claimed"] == 0


def test_revoked_device_is_not_used_by_future_worker_attempt(clients, db, monkeypatch):
    configure_notifications(monkeypatch, provider="unipush_bridge")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_URL", "https://bridge.example.invalid/push")
    monkeypatch.setenv("UNI_PUSH_BRIDGE_TOKEN", BRIDGE_TOKEN)
    get_settings.cache_clear()
    a, _ = clients
    device = register(a).json()
    assert a.delete(f"/api/v1/notification-devices/{device['id']}").status_code == 200
    job, _ = make_due(db, a)

    class Client:
        def post(self, *args, **kwargs):
            raise AssertionError("Revoked device must never reach bridge")

    result = process_once(
        factory=lambda: nullcontext(db),
        provider=UniPushBridgeProvider(get_settings(), Client()),
    )
    assert result["failed"] == 1
    assert job.error_code == "NO_ACTIVE_DEVICE"
    assert job.provider_message_id is None
