"""Deterministic schedule calculation, explicit confirmation and lifecycle operations."""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import utc_now
from app.models.entities import (
    NotificationJob,
    OutingTask,
    Reminder,
    TaskAuditLog,
    User,
)
from app.tasks.repository import draft_data, missing_fields, owned_draft
from app.tasks.time_parse import ZONE

PREVIEW_TTL = timedelta(minutes=5)
INACTIVE = {"cancelled", "completed", "expired"}
CANCELLABLE_JOB_STATUSES = ("queued", "retry_scheduled", "failed")


def aware(value):
    return value.replace(tzinfo=UTC).isoformat() if value else None


def from_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


def local_to_utc(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZONE)
    return value.astimezone(UTC).replace(tzinfo=None)


def task_data(db, task):
    jobs = db.scalars(
        select(NotificationJob)
        .where(
            NotificationJob.user_id == task.user_id,
            NotificationJob.outing_task_id == task.id,
        )
        .order_by(NotificationJob.created_at, NotificationJob.id)
    ).all()
    return {
        "id": task.id,
        "draft_id": task.draft_id,
        "kind": task.kind,
        "title": task.title,
        "status": task.status,
        "revision": task.revision,
        "time_semantics": task.time_semantics,
        "target_at": aware(task.target_at),
        "timezone": task.timezone,
        "origin": task.origin,
        "destination": task.destination,
        "transport": task.transport,
        "departure_at": aware(task.departure_at),
        "reminder_at": aware(task.reminder_at),
        "route_snapshot": task.route_snapshot,
        "weather_snapshot": task.weather_snapshot,
        "calculation_basis": task.calculation_basis,
        "provider": task.provider,
        "is_synthetic": task.is_synthetic,
        "confirmed_at": aware(task.confirmed_at),
        "departed_at": aware(task.departed_at),
        "cancelled_at": aware(task.cancelled_at),
        "completed_at": aware(task.completed_at),
        "navigation_url": (
            "https://uri.amap.com/search?keyword="
            f"{quote(task.destination or '目的地', safe='')}"
            "&src=silver-economy&coordinate=gaode&callnative=1"
        ),
        "notifications": [
            {
                "id": job.id,
                "status": job.status,
                "channel": job.channel,
                "scheduled_at": aware(job.scheduled_at),
                "attempts": job.attempts,
                "provider": job.provider,
                "provider_message_id": job.provider_message_id,
                "last_attempt_at": aware(job.last_attempt_at),
                "error_code": job.error_code,
                "completed_at": aware(job.completed_at),
                "is_mock": job.provider == "mock",
            }
            for job in jobs
        ],
    }


def owned_task(db, user_id, task_id, *, lock=False):
    if lock:
        db.scalar(select(User).where(User.id == user_id).with_for_update())
    statement = select(OutingTask).where(OutingTask.user_id == user_id, OutingTask.id == task_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    task = db.scalar(statement)
    if task is None:
        raise ApiError(404, "NOT_FOUND", "任务不存在或无法访问")
    return task


def calculation(
    *,
    kind,
    time_semantics,
    target_at,
    map_snapshot,
    access_buffer_minutes,
    contingency_buffer_minutes,
    lead_minutes,
    now,
    operation="schedule_preview",
):
    if target_at <= now:
        raise ApiError(422, "TARGET_TIME_PAST", "目标时间已经过去，请重新选择日期和时间")
    route = (map_snapshot or {}).get("route") or {}
    weather = (map_snapshot or {}).get("weather") or {}
    route_seconds = route.get("duration_seconds")
    snapshot_expired = bool(
        map_snapshot
        and map_snapshot.get("expires_at")
        and from_timestamp(map_snapshot["expires_at"]) <= now
    )
    if kind == "outing" and time_semantics == "arrival":
        if not route_seconds:
            raise ApiError(
                422,
                "ROUTE_REQUIRED_FOR_ARRIVAL",
                "到达时间需要可靠的参考车程；请先查询路线，或改为普通时间提醒",
            )
        if snapshot_expired:
            raise ApiError(422, "ROUTE_STALE", "路线参考已过期；请重新查询路线后再计算到达时间")
        departure_at = target_at - timedelta(
            seconds=int(route_seconds),
            minutes=access_buffer_minutes + contingency_buffer_minutes,
        )
        formula = (
            "arrival_at - route_duration_seconds - access_buffer_minutes "
            "- contingency_buffer_minutes"
        )
    elif kind == "outing":
        departure_at = target_at
        formula = "explicit_departure_at"
    else:
        departure_at = target_at
        formula = "reminder_target_at"
    reminder_at = departure_at - timedelta(minutes=lead_minutes)
    if reminder_at <= now:
        raise ApiError(
            422,
            "REMINDER_TIME_PAST",
            "提醒时间已经过去，请缩短提前量或重新选择时间",
        )
    target_local_date = target_at.replace(tzinfo=UTC).astimezone(ZONE).date().isoformat()
    weather_advice = None
    weather_status = "not_applicable"
    if kind == "outing" and map_snapshot:
        if (
            not snapshot_expired
            and weather.get("status") == "available"
            and weather.get("date") == target_local_date
        ):
            weather_status = "available"
            weather_advice = weather.get("umbrella_advice")
        elif snapshot_expired:
            weather_status = "stale"
        elif weather:
            weather_status = "unavailable"
    return {
        "semantics": time_semantics if kind == "outing" else "at",
        "target_at": aware(target_at),
        "departure_at": aware(departure_at),
        "reminder_at": aware(reminder_at),
        "route_duration_seconds": int(route_seconds) if route_seconds else None,
        "route_distance_m": route.get("distance_m"),
        "route_reference_status": (
            "not_applicable"
            if kind == "reminder" or not map_snapshot
            else "stale"
            if snapshot_expired
            else "available"
            if route_seconds
            else "unavailable"
        ),
        "route_expires_at": (map_snapshot or {}).get("expires_at"),
        "weather_reference_status": weather_status,
        "weather_advice": weather_advice,
        "formula": formula,
        "route_subtracted": kind == "outing" and time_semantics == "arrival",
        "inputs": {
            "access_buffer_minutes": access_buffer_minutes,
            "contingency_buffer_minutes": contingency_buffer_minutes,
            "lead_minutes": lead_minutes,
        },
        "provider": (map_snapshot or {}).get("provider", "none"),
        "is_synthetic": bool((map_snapshot or {}).get("is_synthetic", False)),
        "calculated_at": aware(now),
        "operation": operation,
    }


def schedule_preview(db, user_id, draft_id, payload):
    draft = owned_draft(db, user_id, draft_id, lock=True)
    requested = str(payload.client_request_id)
    inputs = {
        "expected_revision": payload.expected_revision,
        "access_buffer_minutes": payload.access_buffer_minutes,
        "contingency_buffer_minutes": payload.contingency_buffer_minutes,
        "lead_minutes": payload.lead_minutes,
    }
    if (
        draft.schedule_preview
        and draft.schedule_preview.get("request_id") == requested
        and draft.schedule_preview.get("inputs") == inputs
        and draft.schedule_preview.get("status") == "ready"
    ):
        return draft_data(draft)
    if draft.status != "confirmed":
        raise ApiError(
            409,
            "INFORMATION_CONFIRMATION_REQUIRED",
            "请先单独确认草案信息，再计算并安排提醒",
        )
    if draft.revision != payload.expected_revision:
        raise ApiError(409, "TASK_DRAFT_STALE", "草案已更新，请重新读取后核对")
    if missing_fields(draft):
        raise ApiError(
            422, "TASK_DRAFT_INCOMPLETE", "请先补全：" + "、".join(missing_fields(draft))
        )
    now = utc_now()
    values = calculation(
        kind=draft.kind,
        time_semantics=draft.time_semantics,
        target_at=draft.target_at,
        map_snapshot=draft.map_snapshot,
        access_buffer_minutes=payload.access_buffer_minutes,
        contingency_buffer_minutes=payload.contingency_buffer_minutes,
        lead_minutes=payload.lead_minutes,
        now=now,
    )
    draft.access_buffer_minutes = payload.access_buffer_minutes
    draft.contingency_buffer_minutes = payload.contingency_buffer_minutes
    draft.lead_minutes = payload.lead_minutes
    draft.revision += 1
    draft.schedule_preview = {
        **values,
        "request_id": requested,
        "draft_revision": draft.revision,
        "status": "ready",
        "created_at": aware(now),
        "expires_at": aware(now + PREVIEW_TTL),
        "inputs": inputs,
    }
    db.commit()
    return draft_data(draft)


def _payload_for_job(task, reminder, draft):
    return {
        "title": task.title,
        "target_at": aware(task.target_at),
        "departure_at": aware(task.departure_at),
        "reminder_at": aware(task.reminder_at),
        "kind": task.kind,
        "origin": task.origin,
        "destination": task.destination,
        "transport": task.transport,
        "weather_advice": (task.weather_snapshot or {}).get("umbrella_advice"),
        "timezone": task.timezone,
        "draft_id": draft.id,
        "source_excerpt": draft.source_excerpt,
        "provider_note": "Mock站内通知；不能证明手机已收到",
    }


def _add_reminder_and_job(db, task):
    settings = get_settings()
    reminder = Reminder(
        user_id=task.user_id,
        outing_task_id=task.id,
        task_revision=task.revision,
        title=task.title,
        due_at=task.reminder_at,
        timezone=task.timezone,
        status="pending",
    )
    db.add(reminder)
    db.flush()
    job = NotificationJob(
        user_id=task.user_id,
        outing_task_id=task.id,
        reminder_id=reminder.id,
        task_revision=task.revision,
        channel="in_app_mock" if settings.notifications_provider == "mock" else "android_device",
        scheduled_at=task.reminder_at,
        status="queued",
        attempts=0,
        max_attempts=3,
        idempotency_key=f"{task.id}:revision-{task.revision}:reminder",
        payload={},
        provider=settings.notifications_provider,
    )
    db.add(job)
    return reminder, job


def confirm_schedule(db, user_id, draft_id, payload):
    requested = str(payload.client_request_id)
    existing = db.scalar(
        select(OutingTask).where(
            OutingTask.user_id == user_id,
            OutingTask.idempotency_key == requested,
        )
    )
    if existing:
        if existing.draft_id != draft_id:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "确认编号已用于其他草案")
        return task_data(db, existing)
    draft = owned_draft(db, user_id, draft_id, lock=True)
    existing = db.scalar(
        select(OutingTask).where(
            OutingTask.user_id == user_id,
            OutingTask.idempotency_key == requested,
        )
    )
    if existing:
        if existing.draft_id != draft_id:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "确认编号已用于其他草案")
        return task_data(db, existing)
    if not draft.schedule_preview:
        raise ApiError(409, "SCHEDULE_PREVIEW_REQUIRED", "请先生成并核对完整提醒预览")
    preview = draft.schedule_preview
    if (
        draft.revision != payload.expected_revision
        or preview.get("draft_revision") != draft.revision
    ):
        raise ApiError(409, "TASK_DRAFT_STALE", "草案已更新，请重新生成提醒预览")
    if preview.get("status") != "ready" or from_timestamp(preview["expires_at"]) <= utc_now():
        raise ApiError(409, "SCHEDULE_PREVIEW_EXPIRED", "提醒预览已过期，请重新生成")
    if draft.status != "confirmed":
        raise ApiError(409, "INFORMATION_CONFIRMATION_REQUIRED", "请先确认草案信息")
    if draft.scheduled_task_id:
        raise ApiError(409, "TASK_ALREADY_SCHEDULED", "此草案已安排提醒")
    route = (draft.map_snapshot or {}).get("route")
    weather = (draft.map_snapshot or {}).get("weather")
    now = utc_now()
    task = OutingTask(
        user_id=user_id,
        draft_id=draft.id,
        source_message_id=draft.source_message_id,
        kind=draft.kind,
        title=draft.title,
        status="scheduled",
        revision=1,
        time_semantics=preview["semantics"],
        target_at=from_timestamp(preview["target_at"]),
        timezone=draft.timezone,
        origin=draft.origin,
        destination=draft.destination,
        transport=draft.transport,
        route_snapshot=route,
        weather_snapshot=weather,
        calculation_basis={k: v for k, v in preview.items() if k != "draft_revision"},
        departure_at=from_timestamp(preview["departure_at"]),
        reminder_at=from_timestamp(preview["reminder_at"]),
        provider="mock",
        is_synthetic=draft.is_synthetic or bool(preview.get("is_synthetic")),
        idempotency_key=requested,
        preview_id=preview["request_id"],
        confirmed_at=now,
    )
    db.add(task)
    db.flush()
    reminder, job = _add_reminder_and_job(db, task)
    job.payload = _payload_for_job(task, reminder, draft)
    draft.status = "scheduled"
    draft.scheduled_task_id = task.id
    draft.revision += 1
    draft.schedule_preview = {**preview, "status": "confirmed", "task_id": task.id}
    db.add(
        TaskAuditLog(
            user_id=user_id,
            outing_task_id=task.id,
            event_type="task_scheduled",
            actor="user",
            task_revision=task.revision,
            payload={
                "draft_revision": preview["draft_revision"],
                "departure_at": aware(task.departure_at),
                "reminder_at": aware(task.reminder_at),
            },
        )
    )
    db.commit()
    return task_data(db, task)


def list_tasks(db, user_id, limit=100):
    rows = db.scalars(
        select(OutingTask)
        .where(OutingTask.user_id == user_id)
        .order_by(OutingTask.created_at.desc(), OutingTask.id.desc())
        .limit(limit)
    ).all()
    return {"items": [task_data(db, row) for row in rows]}


def update_task(db, user_id, task_id, payload):
    task = owned_task(db, user_id, task_id, lock=True)
    if task.revision != payload.expected_revision:
        raise ApiError(409, "TASK_STALE", "任务已更新，请重新读取后修改")
    if task.status != "scheduled":
        raise ApiError(409, "TASK_NOT_EDITABLE", "只有待提醒的任务可以修改")
    now = utc_now()
    target_at = local_to_utc(payload.target_at)
    values = calculation(
        kind=task.kind,
        time_semantics=task.time_semantics,
        target_at=target_at,
        map_snapshot=(
            {
                "route": task.route_snapshot,
                "weather": task.weather_snapshot,
                "expires_at": (task.calculation_basis or {}).get("route_expires_at"),
                "provider": (task.calculation_basis or {}).get("provider", "none"),
                "is_synthetic": bool(
                    (task.calculation_basis or {}).get("is_synthetic", task.is_synthetic)
                ),
            }
            if task.route_snapshot or task.weather_snapshot
            else None
        ),
        access_buffer_minutes=payload.access_buffer_minutes,
        contingency_buffer_minutes=payload.contingency_buffer_minutes,
        lead_minutes=payload.lead_minutes,
        now=now,
        operation="modification",
    )
    db.execute(
        update(NotificationJob)
        .where(
            NotificationJob.user_id == user_id,
            NotificationJob.outing_task_id == task.id,
            NotificationJob.status.in_(CANCELLABLE_JOB_STATUSES),
        )
        .values(status="cancelled", completed_at=now, error_code="SUPERSEDED_BY_MODIFICATION")
    )
    db.execute(
        update(Reminder)
        .where(
            Reminder.user_id == user_id,
            Reminder.outing_task_id == task.id,
            Reminder.status.in_(["pending", "failed"]),
        )
        .values(status="cancelled")
    )
    task.title = payload.title
    task.target_at = target_at
    task.departure_at = from_timestamp(values["departure_at"])
    task.reminder_at = from_timestamp(values["reminder_at"])
    task.revision += 1
    task.calculation_basis = values
    draft = owned_draft(db, user_id, task.draft_id)
    reminder, job = _add_reminder_and_job(db, task)
    job.payload = _payload_for_job(task, reminder, draft)
    db.add(
        TaskAuditLog(
            user_id=user_id,
            outing_task_id=task.id,
            event_type="task_modified",
            actor="user",
            task_revision=task.revision,
            payload={
                "target_at": aware(task.target_at),
                "departure_at": aware(task.departure_at),
                "reminder_at": aware(task.reminder_at),
            },
        )
    )
    db.commit()
    return task_data(db, task)


def transition_task(db, user_id, task_id, payload, desired):
    task = owned_task(db, user_id, task_id, lock=True)
    if task.status == desired and task.revision in {
        payload.expected_revision,
        payload.expected_revision + 1,
    }:
        return task_data(db, task)
    if task.revision != payload.expected_revision:
        raise ApiError(409, "TASK_STALE", "任务已更新，请重新读取后再操作")
    allowed = {"scheduled"}
    if desired == "completed":
        allowed.add("departed")
    if task.status not in allowed:
        raise ApiError(409, "TASK_NOT_ACTIVE", "任务当前状态不允许此操作")
    now = utc_now()
    task.status = desired
    task.revision += 1
    if desired == "cancelled":
        task.cancelled_at = now
    else:
        task.completed_at = now
    cancelled = db.execute(
        update(NotificationJob)
        .where(
            NotificationJob.user_id == user_id,
            NotificationJob.outing_task_id == task.id,
            NotificationJob.status.in_(CANCELLABLE_JOB_STATUSES),
        )
        .values(status="cancelled", completed_at=now)
    ).rowcount
    db.execute(
        update(Reminder)
        .where(
            Reminder.user_id == user_id,
            Reminder.outing_task_id == task.id,
            Reminder.status.in_(["pending", "failed"]),
        )
        .values(status=desired)
    )
    draft = owned_draft(db, user_id, task.draft_id)
    draft.status = desired
    db.add(
        TaskAuditLog(
            user_id=user_id,
            outing_task_id=task.id,
            event_type=f"task_{desired}",
            actor="user",
            task_revision=task.revision,
            payload={
                "cancelled_future_jobs": cancelled,
                "in_flight_or_completed_jobs_preserved": True,
            },
        )
    )
    db.commit()
    return task_data(db, task)


def depart_task(db, user_id, task_id, payload):
    task = owned_task(db, user_id, task_id, lock=True)
    if task.status == "departed" and task.revision in {
        payload.expected_revision,
        payload.expected_revision + 1,
    }:
        return task_data(db, task)
    if task.revision != payload.expected_revision:
        raise ApiError(409, "TASK_STALE", "任务已更新，请重新读取后再操作")
    if task.status != "scheduled":
        raise ApiError(409, "TASK_NOT_ACTIVE", "任务当前状态不允许标记已出发")
    now = utc_now()
    task.status = "departed"
    task.departed_at = now
    task.revision += 1
    cancelled = db.execute(
        update(NotificationJob)
        .where(
            NotificationJob.user_id == user_id,
            NotificationJob.outing_task_id == task.id,
            NotificationJob.status.in_(CANCELLABLE_JOB_STATUSES),
        )
        .values(status="cancelled", completed_at=now, error_code="USER_ALREADY_DEPARTED")
    ).rowcount
    db.execute(
        update(Reminder)
        .where(
            Reminder.user_id == user_id,
            Reminder.outing_task_id == task.id,
            Reminder.status.in_(["pending", "failed"]),
        )
        .values(status="cancelled")
    )
    draft = owned_draft(db, user_id, task.draft_id)
    draft.status = "departed"
    db.add(
        TaskAuditLog(
            user_id=user_id,
            outing_task_id=task.id,
            event_type="task_departed",
            actor="user",
            task_revision=task.revision,
            payload={"cancelled_future_jobs": cancelled},
        )
    )
    db.commit()
    return task_data(db, task)


def record_feedback(db, user_id, task_id, payload):
    task = owned_task(db, user_id, task_id)
    if task.revision != payload.expected_revision:
        raise ApiError(409, "TASK_STALE", "任务已更新，请重新读取后再反馈")
    db.add(
        TaskAuditLog(
            user_id=user_id,
            outing_task_id=task.id,
            event_type="user_feedback",
            actor="user",
            task_revision=task.revision,
            payload={"feedback": payload.feedback, "note": payload.note.strip()},
        )
    )
    db.commit()
    return task_data(db, task)
