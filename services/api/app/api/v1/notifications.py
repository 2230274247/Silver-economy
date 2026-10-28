from datetime import UTC

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import CurrentUser, DatabaseSession, utc_now
from app.models.entities import NotificationDevice, NotificationJob, OutingTask
from app.notifications.device_crypto import (
    device_fingerprint,
    encrypt_client_id,
)
from app.schemas.notifications import (
    DeviceRegistration,
    NotificationDeviceOut,
    NotificationDevicePage,
    NotificationRecordPage,
    NotificationStatusOut,
)

router = APIRouter(prefix="/api/v1")


def aware(value):
    return value.replace(tzinfo=UTC).isoformat() if value else None


def device_data(device):
    return {
        "id": device.id,
        "platform": device.platform,
        "permission_status": device.permission_status,
        "app_version": device.app_version,
        "device_label": device.device_label,
        "can_receive": device.permission_status in {"granted", "provisional"}
        and device.revoked_at is None,
        "last_seen_at": aware(device.last_seen_at),
        "revoked_at": aware(device.revoked_at),
    }


@router.get("/notifications/status", response_model=NotificationStatusOut)
def notification_status():
    settings = get_settings()
    key_configured = bool(settings.notification_device_encryption_key.get_secret_value().strip())
    provider_configured = settings.notifications_provider == "mock" or (
        settings.notifications_provider == "unipush_bridge"
        and bool(settings.uni_push_bridge_url)
        and bool(settings.uni_push_bridge_token.get_secret_value().strip())
    )
    return {
        "provider": settings.notifications_provider,
        "configured": provider_configured,
        "device_encryption_configured": key_configured,
        "physical_delivery_verified": False,
        "explanation": (
            "Mock 仅验证站内 outbox，不能证明手机收到。"
            if settings.notifications_provider == "mock"
            else "服务商接受请求不等于手机送达；真机后台通知必须单独验收。"
        ),
    }


@router.get("/notification-devices", response_model=NotificationDevicePage)
def list_devices(user: CurrentUser, db: DatabaseSession):
    rows = db.scalars(
        select(NotificationDevice)
        .where(NotificationDevice.user_id == user.id)
        .order_by(NotificationDevice.last_seen_at.desc(), NotificationDevice.id.desc())
    ).all()
    return {"items": [device_data(device) for device in rows]}


@router.post(
    "/notification-devices",
    response_model=NotificationDeviceOut,
    status_code=201,
)
def register_device(
    payload: DeviceRegistration,
    user: CurrentUser,
    db: DatabaseSession,
):
    settings = get_settings()
    ciphertext = encrypt_client_id(settings, payload.push_client_id)
    fingerprint = device_fingerprint(settings, payload.push_client_id)
    now = utc_now()

    # A physical device can belong to only one account at a time. Reassigning it
    # revokes every stale owner before this user becomes eligible for delivery.
    stale_devices = db.scalars(
        select(NotificationDevice)
        .where(
            NotificationDevice.fingerprint == fingerprint,
            NotificationDevice.user_id != user.id,
            NotificationDevice.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    for stale in stale_devices:
        stale.revoked_at = now
        stale.last_seen_at = now

    device = db.scalar(
        select(NotificationDevice)
        .where(
            NotificationDevice.user_id == user.id,
            NotificationDevice.fingerprint == fingerprint,
        )
        .with_for_update()
    )
    if device is None:
        device = NotificationDevice(
            user_id=user.id,
            platform=payload.platform,
            push_client_id_ciphertext=ciphertext,
            fingerprint=fingerprint,
            permission_status=payload.permission_status,
            app_version=payload.app_version,
            device_label=payload.device_label,
            last_seen_at=now,
            revoked_at=None,
        )
        db.add(device)
    else:
        device.push_client_id_ciphertext = ciphertext
        device.permission_status = payload.permission_status
        device.app_version = payload.app_version
        device.device_label = payload.device_label
        device.last_seen_at = now
        device.revoked_at = None
    db.commit()
    db.refresh(device)
    return device_data(device)


@router.delete("/notification-devices/{device_id}", response_model=NotificationDeviceOut)
def revoke_device(device_id: str, user: CurrentUser, db: DatabaseSession):
    device = db.scalar(
        select(NotificationDevice)
        .where(
            NotificationDevice.id == device_id,
            NotificationDevice.user_id == user.id,
        )
        .with_for_update()
    )
    if device is None:
        raise ApiError(404, "NOT_FOUND", "设备不存在或无法访问")
    device.revoked_at = utc_now()
    db.commit()
    db.refresh(device)
    return device_data(device)


@router.get("/notifications", response_model=NotificationRecordPage)
def list_notifications(
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(100, ge=1, le=200),
):
    rows = db.execute(
        select(NotificationJob, OutingTask.title)
        .join(
            OutingTask,
            (OutingTask.id == NotificationJob.outing_task_id)
            & (OutingTask.user_id == NotificationJob.user_id),
        )
        .where(NotificationJob.user_id == user.id)
        .order_by(NotificationJob.created_at.desc(), NotificationJob.id.desc())
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": job.id,
                "outing_task_id": job.outing_task_id,
                "title": title,
                "status": job.status,
                "channel": job.channel,
                "scheduled_at": aware(job.scheduled_at),
                "attempts": job.attempts,
                "provider": job.provider,
                "is_mock": job.provider == "mock",
                "provider_message_id": job.provider_message_id,
                "last_attempt_at": aware(job.last_attempt_at),
                "error_code": job.error_code,
                "completed_at": aware(job.completed_at),
            }
            for job, title in rows
        ]
    }
