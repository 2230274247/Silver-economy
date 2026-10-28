"""A deterministic source-linked event view, never an invented narrative summary."""

from datetime import UTC
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select

from app.core.errors import ApiError
from app.models.entities import MemoryFact, MemorySource, Message


def event_label(fact):
    if fact.event_at is None or fact.event_precision not in {"year", "month", "day"}:
        return "发生时间未明确"
    value = fact.event_at.replace(tzinfo=UTC).astimezone(ZoneInfo(fact.event_timezone))
    return value.strftime(
        {"year": "%Y年", "month": "%Y年%m月", "day": "%Y年%m月%d日"}[fact.event_precision]
    )


def timeline_page(db, user_id, *, provider, before_id=None, limit=30):
    # Coarse dates are calendar anchors, not asserted exact dates. Unknown time
    # uses recording order and is explicitly labelled in the response/UI.
    sort_at = case(
        (
            and_(
                MemoryFact.event_at.is_not(None),
                MemoryFact.event_precision.in_(["year", "month", "day"]),
            ),
            MemoryFact.event_at,
        ),
        else_=MemoryFact.recorded_at,
    )
    sources = (
        select(MemorySource.id)
        .join(
            Message,
            and_(Message.id == MemorySource.message_id, Message.user_id == MemorySource.user_id),
        )
        .where(
            MemorySource.memory_id == MemoryFact.id,
            MemorySource.user_id == user_id,
            Message.role == "user",
            Message.content != "",
        )
        .exists()
    )
    statement = select(MemoryFact, sort_at.label("sort_at")).where(
        MemoryFact.user_id == user_id,
        MemoryFact.deleted_at.is_(None),
        sources,
    )
    if provider == "mock":
        statement = statement.where(
            or_(
                MemoryFact.extractor_provider.in_(["mock", "synthetic", "manual"]),
                MemoryFact.extractor_provider.is_(None),
            )
        )
    else:
        statement = statement.where(
            or_(MemoryFact.extractor_provider != "mock", MemoryFact.extractor_provider.is_(None))
        )
    if before_id:
        anchor = db.execute(statement.where(MemoryFact.id == before_id)).first()
        if anchor is None:
            raise ApiError(404, "NOT_FOUND", "时间线位置不存在或无法访问")
        fact, at = anchor
        statement = statement.where(
            or_(
                sort_at < at,
                and_(sort_at == at, MemoryFact.recorded_at < fact.recorded_at),
                and_(
                    sort_at == at,
                    MemoryFact.recorded_at == fact.recorded_at,
                    MemoryFact.id < fact.id,
                ),
            )
        )
    rows = db.execute(
        statement.order_by(
            sort_at.desc(), MemoryFact.recorded_at.desc(), MemoryFact.id.desc()
        ).limit(limit + 1)
    ).all()
    more, facts = len(rows) > limit, [r[0] for r in rows[:limit]]
    ids = [f.id for f in facts]
    counts = (
        dict(
            db.execute(
                select(MemorySource.memory_id, func.count(MemorySource.id))
                .join(
                    Message,
                    and_(
                        Message.id == MemorySource.message_id,
                        Message.user_id == MemorySource.user_id,
                    ),
                )
                .where(
                    MemorySource.user_id == user_id,
                    MemorySource.memory_id.in_(ids),
                    Message.role == "user",
                    Message.content != "",
                )
                .group_by(MemorySource.memory_id)
            ).all()
        )
        if ids
        else {}
    )
    return facts, counts, facts[-1].id if more else None
