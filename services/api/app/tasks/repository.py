"""Owned, revisioned information drafts. Confirmation here never schedules a job."""

import re
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.errors import ApiError
from app.core.security import utc_now
from app.llm.providers import ProviderFailure
from app.models.entities import TaskDraft, User
from app.tasks.intent import NEW_TASK, TEXT_FIELDS, grounded, negated_modes
from app.tasks.time_parse import calendar_day, clock_value, number, parse_target, time_parts


def stamp(value):
    return value.replace(tzinfo=UTC).isoformat() if value else None


def missing_fields(draft):
    missing = []
    if draft.target_at is None:
        if calendar_day(draft.date_text, draft.time_reference_at) is None:
            missing.append("明确的日期")
        if not draft.clock_text:
            missing.append("具体时刻")
        elif clock_value(draft.clock_text, draft.period_text) is None:
            missing.append("上午/下午或明确的24小时制时刻")
    elif draft.target_at <= utc_now():
        missing.append("尚未过去的时间")
    if draft.kind == "outing":
        if draft.time_semantics not in {"arrival", "departure"}:
            missing.append("到达还是出发")
        for field, label in (("destination", "目的地"), ("origin", "出发地")):
            if not getattr(draft, field).strip():
                missing.append(label)
        if draft.transport == "unknown":
            missing.append("交通方式")
    return missing


def draft_data(draft):
    day = calendar_day(draft.date_text, draft.time_reference_at)
    data = {
        name: getattr(draft, name)
        for name in (
            "id",
            "conversation_id",
            "source_message_id",
            "last_message_id",
            "source_excerpt",
            "kind",
            "title",
            "status",
            "revision",
            "date_text",
            "clock_text",
            "period_text",
            "timezone",
            "time_semantics",
            "origin",
            "destination",
            "transport",
            "lead_minutes",
            "evidence",
            "extractor_provider",
            "is_synthetic",
            "location_consent",
            "origin_place",
            "destination_place",
            "map_snapshot",
            "access_buffer_minutes",
            "contingency_buffer_minutes",
            "schedule_preview",
            "scheduled_task_id",
        )
    }
    data.update(
        target_at=stamp(draft.target_at),
        confirmed_at=stamp(draft.confirmed_at),
        missing_fields=missing_fields(draft),
        scheduling_status=(
            draft.status
            if draft.status in {"scheduled", "cancelled", "completed"}
            else "not_scheduled"
        ),
        time_reference_at=stamp(draft.time_reference_at),
        resolved_date=day.isoformat() if day else None,
    )
    if draft.map_snapshot:
        expires = datetime.fromisoformat(draft.map_snapshot["expires_at"])
        data["map_snapshot"] = {
            **draft.map_snapshot,
            "expired": expires <= utc_now().replace(tzinfo=UTC),
        }
    return data


def owned_draft(db, user_id, draft_id, *, lock=False):
    if lock:
        db.scalar(select(User).where(User.id == user_id).with_for_update())
    statement = select(TaskDraft).where(TaskDraft.user_id == user_id, TaskDraft.id == draft_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    draft = db.scalar(statement)
    if draft is None:
        raise ApiError(404, "NOT_FOUND", "草案不存在或无法访问")
    return draft


def task_map(db, user_id, messages):
    replies = {m.reply_to_message_id: m.id for m in messages if m.role == "assistant"}
    result = {}
    if replies:
        for draft in db.scalars(
            select(TaskDraft)
            .where(TaskDraft.user_id == user_id, TaskDraft.last_message_id.in_(replies))
            .order_by(TaskDraft.ordinal, TaskDraft.id)
        ):
            result.setdefault(replies[draft.last_message_id], []).append(draft_data(draft))
    return result


def save_candidates(db, message, candidates, context, provider):
    plans = []
    for candidate in candidates:
        candidate = grounded(candidate, message.content)
        if candidate is None:
            continue
        draft = None
        if candidate.draft_id:
            if candidate.draft_id not in context.revisions:
                raise ProviderFailure("TASK_UNSUPPORTED_REFERENCE")
            draft = db.scalar(
                select(TaskDraft)
                .where(
                    TaskDraft.id == candidate.draft_id,
                    TaskDraft.user_id == message.user_id,
                    TaskDraft.conversation_id == message.conversation_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                draft is None
                or draft.status != "draft"
                or draft.revision != context.revisions[draft.id]
            ):
                raise ProviderFailure("TASK_CHANGED_DURING_REPLY")
            if len(context.revisions) > 1 and not (
                draft.destination and draft.destination in message.content
            ):
                continue  # Several pending arrangements require an explicit choice.
        elif not NEW_TASK.search(message.content):
            continue
        plans.append((draft, candidate))
    ids = [draft.id for draft, _ in plans if draft is not None]
    if len(set(ids)) != len(ids):
        raise ProviderFailure("TASK_DUPLICATE_REFERENCE")
    saved = []
    for ordinal, (draft, candidate) in enumerate(plans):
        if draft is None:
            draft = TaskDraft(
                user_id=message.user_id,
                conversation_id=message.conversation_id,
                source_message_id=message.id,
                last_message_id=message.id,
                ordinal=ordinal,
                kind=candidate.kind,
                title=candidate.source_excerpt.strip()[:160],
                source_excerpt=candidate.source_excerpt,
                time_reference_at=message.created_at,
                date_text="",
                clock_text="",
                period_text="",
                origin="",
                destination="",
                time_semantics="at" if candidate.kind == "reminder" else "unknown",
                transport="unknown",
                lead_minutes=0 if candidate.kind == "reminder" else 60,
                revision=1,
                status="draft",
                evidence={},
                extractor_provider=provider,
                is_synthetic=provider == "mock" or "Synthetic" in message.content,
            )
            db.add(draft)
        else:
            draft.revision += 1
        evidence = dict(draft.evidence)
        for field in (*TEXT_FIELDS, "transport", "time_semantics"):
            value = getattr(candidate, field)
            if not value or value == "unknown":
                continue
            setattr(draft, field, value)
            evidence[field] = {
                "origin": "chat",
                "message_id": message.id,
                "source_excerpt": candidate.source_excerpt,
                "value": value,
            }
        if candidate.date_text:
            draft.time_reference_at = message.created_at
        if draft.transport in negated_modes(candidate.source_excerpt):
            draft.transport = "unknown"
            evidence["transport"] = {
                "origin": "chat_withdrawal",
                "message_id": message.id,
                "source_excerpt": candidate.source_excerpt,
                "value": "unknown",
            }
        if draft.kind == "reminder":
            draft.time_semantics = "at"
        if lead := re.search(
            r"提前(半|[0-9零一二两三四五六七八九十]+)(?:个)?(小时|分钟)", message.content
        ):
            minutes = (
                30
                if lead[1] == "半" and lead[2] == "小时"
                else number(lead[1]) * (60 if lead[2] == "小时" else 1)
            )
            if 0 <= minutes <= 10080:
                draft.lead_minutes = minutes
                evidence["lead_minutes"] = {
                    "origin": "chat",
                    "message_id": message.id,
                    "source_excerpt": lead[0],
                    "value": minutes,
                }
        draft.evidence = evidence
        draft.target_at = parse_target(
            draft.date_text, draft.clock_text, draft.period_text, draft.time_reference_at
        )
        draft.last_message_id = message.id
        invalidate_map_snapshot(draft)
        saved.append(draft)
    db.flush()
    return saved


def draft_reply(drafts, provider):
    prefix = "【Mock 意图测试】" if provider == "mock" else ""
    if not drafts:
        return prefix + "本次未创建或更新提醒。请明确事项；若有多条草案，请在对应卡片补充。"
    missing = list(dict.fromkeys(field for draft in drafts for field in missing_fields(draft)))
    question = "还需要确认：" + "、".join(missing) + "。" if missing else "请核对下面的草案。"
    return prefix + question + "信息可编辑、确认后保存；提醒尚未安排，当前不会主动通知。"


def update_draft(db, user_id, draft_id, payload):
    draft = owned_draft(db, user_id, draft_id, lock=True)
    if draft.revision != payload.expected_revision:
        raise ApiError(409, "TASK_DRAFT_STALE", "草案已更新，请重新读取后核对")
    if draft.status == "deferred":
        raise ApiError(409, "TASK_DRAFT_DEFERRED", "此草案已暂不安排，请重新提出事项")
    if draft.status in {"scheduled", "cancelled", "completed"}:
        raise ApiError(
            409,
            "TASK_DRAFT_ALREADY_SCHEDULED",
            "此草案已进入任务流程，请从提醒详情修改",
        )
    now = utc_now()
    draft.title = payload.title
    date, clock, period = time_parts(payload.time_text)
    if date != draft.date_text:
        draft.time_reference_at = now
    draft.date_text, draft.clock_text, draft.period_text = date, clock, period
    draft.target_at = parse_target(
        draft.date_text, draft.clock_text, draft.period_text, draft.time_reference_at
    )
    draft.time_semantics = "at" if draft.kind == "reminder" else payload.time_semantics
    for field in ("origin", "destination", "transport", "lead_minutes"):
        setattr(draft, field, getattr(payload, field))
    draft.evidence = {
        **draft.evidence,
        **{
            field: {"origin": "user_edit", "value": value, "at": stamp(now)}
            for field, value in payload.model_dump(exclude={"expected_revision"}).items()
        },
        **{
            field: {"origin": "user_edit", "value": getattr(draft, field), "at": stamp(now)}
            for field in ("date_text", "clock_text", "period_text")
        },
    }
    draft.status, draft.confirmed_at = "draft", None
    draft.revision += 1
    invalidate_map_snapshot(draft)
    db.commit()
    return draft_data(draft)


def invalidate_map_snapshot(draft):
    draft.map_snapshot = None
    draft.schedule_preview = None
    draft.scheduled_task_id = None
    for field in ("origin", "destination"):
        place = getattr(draft, field + "_place")
        if place and place["name"] != getattr(draft, field):
            setattr(draft, field + "_place", None)


def act_on_draft(db, user_id, draft_id, payload):
    draft = owned_draft(db, user_id, draft_id, lock=True)
    desired = "confirmed" if payload.action == "confirm" else "deferred"
    if draft.status == desired and payload.expected_revision in {
        draft.revision,
        draft.revision - 1,
    }:
        return draft_data(draft)
    if draft.status in {"scheduled", "cancelled", "completed"}:
        raise ApiError(409, "TASK_DRAFT_ALREADY_SCHEDULED", "此草案已进入任务流程")
    if draft.revision != payload.expected_revision or draft.status != "draft":
        raise ApiError(409, "TASK_DRAFT_STALE", "草案已更新，请重新读取后核对")
    if desired == "confirmed" and missing_fields(draft):
        raise ApiError(
            422, "TASK_DRAFT_INCOMPLETE", "请先补全：" + "、".join(missing_fields(draft))
        )
    draft.status = desired
    draft.confirmed_at = utc_now() if desired == "confirmed" else None
    draft.schedule_preview = None
    draft.revision += 1
    if draft.map_snapshot:
        draft.map_snapshot = (
            {**draft.map_snapshot, "draft_revision": draft.revision}
            if desired == "confirmed"
            else None
        )
    db.commit()
    return draft_data(draft)
