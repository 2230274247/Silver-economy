"""Notification provider contract. Mock delivery is never described as phone delivery."""

import uuid


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


def get_notification_provider(settings):
    if settings.notifications_provider == "mock":
        return MockNotificationProvider()
    raise NotificationFailure("NOTIFICATION_NOT_CONFIGURED")
