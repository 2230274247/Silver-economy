"""Owner-scoped export of user-visible V0.1 data without authentication secrets."""

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.security import CurrentUser, DatabaseSession, utc_now
from app.models.entities import (
    Conversation,
    LifeEvent,
    MapRequest,
    MemoryFact,
    MemoryRevision,
    MemorySource,
    MemoryUse,
    Message,
    ModelUsage,
    NotificationDevice,
    NotificationJob,
    OutingTask,
    Reminder,
    TaskAuditLog,
    TaskDraft,
)

router = APIRouter(prefix="/api/v1")


def timestamp(value: datetime | None):
    return value.replace(tzinfo=UTC).isoformat() if value else None


def owned_rows(db, model, user_id, *order_by):
    statement = select(model).where(model.user_id == user_id)
    if order_by:
        statement = statement.order_by(*order_by)
    return db.scalars(statement).all()


def conversation_data(item):
    return {
        "id": item.id,
        "title": item.title,
        "created_at": timestamp(item.created_at),
        "last_message_at": timestamp(item.last_message_at),
    }


def message_data(item):
    return {
        "id": item.id,
        "conversation_id": item.conversation_id,
        "role": item.role,
        "content": item.content,
        "status": item.status,
        "error_code": item.error_code,
        "provider": item.provider,
        "memory_status": item.memory_status,
        "reply_to_message_id": item.reply_to_message_id,
        "created_at": timestamp(item.created_at),
        "updated_at": timestamp(item.updated_at),
    }


def memory_data(item):
    return {
        "id": item.id,
        "kind": item.kind,
        "key": item.key,
        "value": item.value,
        "status": item.fact_status,
        "valid_from": timestamp(item.valid_from),
        "valid_to": timestamp(item.valid_to),
        "event_at": timestamp(item.event_at),
        "event_precision": item.event_precision,
        "event_timezone": item.event_timezone,
        "time_expression": item.time_expression,
        "state_text": item.state_text,
        "confidence_label": item.confidence_label,
        "recorded_at": timestamp(item.recorded_at),
        "confirmed_at": timestamp(item.confirmed_at),
        "deleted_at": timestamp(item.deleted_at),
        "retrieval_allowed": item.retrieval_allowed,
        "extractor_provider": item.extractor_provider,
        "extractor_version": item.extractor_version,
        "is_synthetic": item.is_synthetic,
        "revision": item.revision,
        "value_origin": item.value_origin,
    }


def revision_data(item):
    return {
        "id": item.id,
        "memory_id": item.memory_id,
        "revision": item.revision,
        "action": item.action,
        "actor": item.actor,
        "before": item.before,
        "after": item.after,
        "created_at": timestamp(item.created_at),
    }


def source_data(item):
    return {
        "id": item.id,
        "memory_id": item.memory_id,
        "message_id": item.message_id,
        "source_excerpt": item.source_excerpt,
        "created_at": timestamp(item.created_at),
    }


def memory_use_data(item):
    return {
        "id": item.id,
        "assistant_message_id": item.assistant_message_id,
        "memory_id": item.memory_id,
        "source_message_id": item.source_message_id,
        "reference_label": item.reference_label,
        "memory_revision": item.memory_revision,
        "created_at": timestamp(item.created_at),
    }


def life_event_data(item):
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "occurred_at": timestamp(item.occurred_at),
        "occurred_precision": item.occurred_precision,
        "recorded_at": timestamp(item.recorded_at),
        "source_memory_id": item.source_memory_id,
        "is_user_confirmed": item.is_user_confirmed,
    }


def draft_data(item):
    return {
        "id": item.id,
        "conversation_id": item.conversation_id,
        "source_message_id": item.source_message_id,
        "last_message_id": item.last_message_id,
        "ordinal": item.ordinal,
        "kind": item.kind,
        "title": item.title,
        "source_excerpt": item.source_excerpt,
        "status": item.status,
        "revision": item.revision,
        "date_text": item.date_text,
        "clock_text": item.clock_text,
        "period_text": item.period_text,
        "time_reference_at": timestamp(item.time_reference_at),
        "target_at": timestamp(item.target_at),
        "timezone": item.timezone,
        "time_semantics": item.time_semantics,
        "origin": item.origin,
        "destination": item.destination,
        "transport": item.transport,
        "lead_minutes": item.lead_minutes,
        "evidence": item.evidence,
        "confirmed_at": timestamp(item.confirmed_at),
        "extractor_provider": item.extractor_provider,
        "is_synthetic": item.is_synthetic,
        "location_consent": item.location_consent,
        "origin_place": item.origin_place,
        "destination_place": item.destination_place,
        "map_snapshot": item.map_snapshot,
        "access_buffer_minutes": item.access_buffer_minutes,
        "contingency_buffer_minutes": item.contingency_buffer_minutes,
        "schedule_preview": item.schedule_preview,
        "scheduled_task_id": item.scheduled_task_id,
        "created_at": timestamp(item.created_at),
        "updated_at": timestamp(item.updated_at),
    }


def outing_task_data(item):
    return {
        "id": item.id,
        "draft_id": item.draft_id,
        "source_message_id": item.source_message_id,
        "kind": item.kind,
        "title": item.title,
        "status": item.status,
        "revision": item.revision,
        "time_semantics": item.time_semantics,
        "target_at": timestamp(item.target_at),
        "timezone": item.timezone,
        "origin": item.origin,
        "destination": item.destination,
        "transport": item.transport,
        "route_snapshot": item.route_snapshot,
        "weather_snapshot": item.weather_snapshot,
        "calculation_basis": item.calculation_basis,
        "departure_at": timestamp(item.departure_at),
        "reminder_at": timestamp(item.reminder_at),
        "provider": item.provider,
        "is_synthetic": item.is_synthetic,
        "confirmed_at": timestamp(item.confirmed_at),
        "departed_at": timestamp(item.departed_at),
        "cancelled_at": timestamp(item.cancelled_at),
        "completed_at": timestamp(item.completed_at),
        "created_at": timestamp(item.created_at),
        "updated_at": timestamp(item.updated_at),
    }


def reminder_data(item):
    return {
        "id": item.id,
        "outing_task_id": item.outing_task_id,
        "title": item.title,
        "due_at": timestamp(item.due_at),
        "timezone": item.timezone,
        "status": item.status,
        "task_revision": item.task_revision,
        "created_at": timestamp(item.created_at),
        "updated_at": timestamp(item.updated_at),
    }


def notification_data(item):
    return {
        "id": item.id,
        "outing_task_id": item.outing_task_id,
        "reminder_id": item.reminder_id,
        "task_revision": item.task_revision,
        "channel": item.channel,
        "scheduled_at": timestamp(item.scheduled_at),
        "status": item.status,
        "attempts": item.attempts,
        "payload": item.payload,
        "provider": item.provider,
        "last_attempt_at": timestamp(item.last_attempt_at),
        "error_code": item.error_code,
        "completed_at": timestamp(item.completed_at),
        "created_at": timestamp(item.created_at),
        "updated_at": timestamp(item.updated_at),
    }


def device_data(item):
    return {
        "platform": item.platform,
        "permission_status": item.permission_status,
        "app_version": item.app_version,
        "device_label": item.device_label,
        "can_receive": item.permission_status in {"granted", "provisional"}
        and item.revoked_at is None,
        "last_seen_at": timestamp(item.last_seen_at),
        "revoked_at": timestamp(item.revoked_at),
        "created_at": timestamp(item.created_at),
        "updated_at": timestamp(item.updated_at),
    }


def audit_data(item):
    return {
        "id": item.id,
        "outing_task_id": item.outing_task_id,
        "event_type": item.event_type,
        "actor": item.actor,
        "task_revision": item.task_revision,
        "payload": item.payload,
        "created_at": timestamp(item.created_at),
    }


def map_request_data(item):
    return {
        "id": item.id,
        "draft_id": item.draft_id,
        "operation": item.operation,
        "provider": item.provider,
        "status": item.status,
        "error_code": item.error_code,
        "result": item.result,
        "context": item.context,
        "expires_at": timestamp(item.expires_at),
        "latency_ms": item.latency_ms,
        "created_at": timestamp(item.created_at),
    }


def usage_data(item):
    return {
        "id": item.id,
        "provider": item.provider,
        "model": item.model,
        "purpose": item.purpose,
        "prompt_version": item.prompt_version,
        "input_tokens": item.input_tokens,
        "output_tokens": item.output_tokens,
        "latency_ms": item.latency_ms,
        "estimated_cost_usd": str(item.estimated_cost) if item.estimated_cost is not None else None,
        "status": item.status,
        "error_code": item.error_code,
        "created_at": timestamp(item.created_at),
    }


def account_export(db, user):
    conversations = owned_rows(
        db,
        Conversation,
        user.id,
        Conversation.created_at,
        Conversation.id,
    )
    messages = owned_rows(db, Message, user.id, Message.created_at, Message.id)
    facts = owned_rows(db, MemoryFact, user.id, MemoryFact.recorded_at, MemoryFact.id)
    revisions = owned_rows(
        db, MemoryRevision, user.id, MemoryRevision.created_at, MemoryRevision.id
    )
    sources = owned_rows(db, MemorySource, user.id, MemorySource.created_at, MemorySource.id)
    uses = owned_rows(db, MemoryUse, user.id, MemoryUse.created_at, MemoryUse.id)
    events = owned_rows(db, LifeEvent, user.id, LifeEvent.recorded_at, LifeEvent.id)
    drafts = owned_rows(db, TaskDraft, user.id, TaskDraft.created_at, TaskDraft.id)
    tasks = owned_rows(db, OutingTask, user.id, OutingTask.created_at, OutingTask.id)
    reminders = owned_rows(db, Reminder, user.id, Reminder.created_at, Reminder.id)
    notifications = owned_rows(
        db, NotificationJob, user.id, NotificationJob.created_at, NotificationJob.id
    )
    devices = owned_rows(
        db, NotificationDevice, user.id, NotificationDevice.created_at, NotificationDevice.id
    )
    audits = owned_rows(db, TaskAuditLog, user.id, TaskAuditLog.created_at, TaskAuditLog.id)
    map_requests = owned_rows(db, MapRequest, user.id, MapRequest.created_at, MapRequest.id)
    usages = owned_rows(db, ModelUsage, user.id, ModelUsage.created_at, ModelUsage.id)
    return {
        "schema_version": "silver-memory-export/v1",
        "generated_at": timestamp(utc_now()),
        "timezone": "Asia/Hong_Kong",
        "account": {
            "login_name": user.login_name,
            "created_at": timestamp(user.created_at),
            "disabled_at": timestamp(user.disabled_at),
            "memory_enabled": user.memory_enabled,
        },
        "data": {
            "conversations": [conversation_data(item) for item in conversations],
            "messages": [message_data(item) for item in messages],
            "memories": [memory_data(item) for item in facts],
            "memory_revisions": [revision_data(item) for item in revisions],
            "memory_sources": [source_data(item) for item in sources],
            "memory_uses": [memory_use_data(item) for item in uses],
            "life_events": [life_event_data(item) for item in events],
            "task_drafts": [draft_data(item) for item in drafts],
            "outing_tasks": [outing_task_data(item) for item in tasks],
            "reminders": [reminder_data(item) for item in reminders],
            "notifications": [notification_data(item) for item in notifications],
            "notification_devices": [device_data(item) for item in devices],
            "task_audit_logs": [audit_data(item) for item in audits],
            "map_requests": [map_request_data(item) for item in map_requests],
            "model_usage": [usage_data(item) for item in usages],
        },
        "excluded_internal_data": [
            "密码哈希",
            "登录令牌哈希",
            "推送客户端 ID 及其加密密文",
            "设备指纹",
            "模型原始响应",
            "通知租约和幂等内部字段",
        ],
    }


@router.get("/account/export")
def export_account(user: CurrentUser, db: DatabaseSession):
    generated = utc_now()
    filename = f"silver-memory-data-{generated:%Y%m%d-%H%M%S}.json"
    payload = jsonable_encoder(account_export(db, user))
    return JSONResponse(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
        },
    )
