"""Notification provider contracts. Provider acceptance never proves phone delivery."""

import uuid

import httpx

from app.notifications.device_crypto import decrypt_client_id


class NotificationFailure(Exception):
    def __init__(self, code, *, retryable=False):
        self.code = code
        self.retryable = retryable


class MockNotificationProvider:
    name = "mock"

    def send(self, task, job):
        return {
            "provider_message_id": f"mock-{uuid.uuid4()}",
            "status": "submitted_to_provider",
            "is_mock": True,
        }


class UniPushBridgeProvider:
    """Minimal authenticated bridge to an operator-owned uniCloud push function."""

    name = "unipush_bridge"

    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client

    def send(self, task, job, device):
        url = self.settings.uni_push_bridge_url
        token = self.settings.uni_push_bridge_token.get_secret_value().strip()
        if not url or not token:
            raise NotificationFailure("NOTIFICATION_NOT_CONFIGURED")
        if device is None:
            raise NotificationFailure("NO_ACTIVE_DEVICE")
        try:
            client_id = decrypt_client_id(
                self.settings,
                device.push_client_id_ciphertext,
            )
        except RuntimeError:
            raise NotificationFailure("NOTIFICATION_DEVICE_CREDENTIAL_UNREADABLE") from None
        body = {
            "client_id": client_id,
            "request_id": job.idempotency_key,
            "notification": {
                "title": "时光有声提醒",
                "body": "您有一项已确认的行程提醒，点按查看详情。",
                "data": {
                    "route": "/pages/reminders/index",
                    "outing_task_id": task.id,
                },
            },
        }
        owns_client = self.client is None
        client = self.client or httpx.Client(timeout=10, follow_redirects=False)
        try:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
        except httpx.HTTPError:
            raise NotificationFailure(
                "PROVIDER_CONNECTION_UNKNOWN",
                retryable=True,
            ) from None
        finally:
            if owns_client:
                client.close()
        if response.status_code >= 500 or response.status_code == 429:
            raise NotificationFailure("PROVIDER_TEMPORARILY_UNAVAILABLE", retryable=True)
        if response.status_code < 200 or response.status_code >= 300:
            raise NotificationFailure("PROVIDER_REJECTED")
        try:
            payload = response.json()
        except ValueError:
            raise NotificationFailure("PROVIDER_RESPONSE_INVALID") from None
        message_id = payload.get("message_id") if isinstance(payload, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise NotificationFailure("PROVIDER_RESPONSE_INVALID")
        return {
            "provider_message_id": message_id[:120],
            "status": "submitted_to_provider",
            "is_mock": False,
        }


def get_notification_provider(settings):
    if settings.notifications_provider == "mock":
        return MockNotificationProvider()
    if settings.notifications_provider == "unipush_bridge":
        return UniPushBridgeProvider(settings)
    raise NotificationFailure("NOTIFICATION_NOT_CONFIGURED")
