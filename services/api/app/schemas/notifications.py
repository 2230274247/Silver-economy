from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Literal["android"] = "android"
    push_client_id: str = Field(min_length=8, max_length=512)
    permission_status: Literal["granted", "denied", "provisional"]
    app_version: str = Field(default="", max_length=64)
    device_label: str = Field(default="", max_length=80)

    @field_validator("push_client_id", "app_version", "device_label")
    @classmethod
    def strip_value(cls, value):
        return value.strip()


class NotificationDeviceOut(BaseModel):
    id: str
    platform: str
    permission_status: str
    app_version: str
    device_label: str
    can_receive: bool
    last_seen_at: datetime
    revoked_at: datetime | None


class NotificationDevicePage(BaseModel):
    items: list[NotificationDeviceOut]


class NotificationRecordOut(BaseModel):
    id: str
    outing_task_id: str
    title: str
    status: str
    channel: str
    scheduled_at: datetime
    attempts: int
    provider: str
    is_mock: bool
    provider_message_id: str | None
    last_attempt_at: datetime | None
    error_code: str | None
    completed_at: datetime | None


class NotificationRecordPage(BaseModel):
    items: list[NotificationRecordOut]


class NotificationStatusOut(BaseModel):
    provider: str
    configured: bool
    device_encryption_configured: bool
    physical_delivery_verified: Literal[False] = False
    explanation: str
