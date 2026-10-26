from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_, select

from app.api.v1.chat import message_data, timestamp
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import CurrentUser, DatabaseSession
from app.models.entities import MemoryFact, MemorySource, Message, User
from app.schemas.memory import MemoryPage, SourcePage

router = APIRouter(prefix="/api/v1")


class Consent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.get("/memory-consent")
def get_consent(user: CurrentUser):
    return {"enabled": user.memory_enabled}


@router.post("/memory-consent")
def set_consent(payload: Consent, user: CurrentUser, db: DatabaseSession):
    owner = db.scalar(select(User).where(User.id == user.id).with_for_update())
    owner.memory_enabled = payload.enabled
    db.commit()
    return {"enabled": owner.memory_enabled}


def memory_data(item):
    return {
        "id": item.id,
        "kind": item.kind,
        "key": item.key,
        "value": item.value,
        "status": item.fact_status,
        "event_at": timestamp(item.event_at),
        "event_precision": item.event_precision,
        "time_expression": item.time_expression,
        "recorded_at": timestamp(item.recorded_at),
        "confirmed_at": timestamp(item.confirmed_at),
        "retrieval_allowed": item.retrieval_allowed,
        "extractor_provider": item.extractor_provider,
        "extractor_version": item.extractor_version,
        "is_synthetic": item.is_synthetic,
    }


def owned_memory(db, user_id, memory_id):
    item = db.scalar(
        select(MemoryFact).where(
            MemoryFact.id == memory_id,
            MemoryFact.user_id == user_id,
            MemoryFact.deleted_at.is_(None),
        )
    )
    if item is None:
        raise ApiError(404, "NOT_FOUND", "记忆不存在或无法访问")
    return item


@router.get("/memories", response_model=MemoryPage)
def list_memories(
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(30, ge=1, le=100),
    before_id: str | None = None,
):
    statement = select(MemoryFact).where(
        MemoryFact.user_id == user.id, MemoryFact.deleted_at.is_(None)
    )
    # Keep Mock extraction records separate from the operator's live view.
    if get_settings().llm_provider == "mock":
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
        anchor = owned_memory(db, user.id, before_id)
        statement = statement.where(
            or_(
                MemoryFact.recorded_at < anchor.recorded_at,
                and_(MemoryFact.recorded_at == anchor.recorded_at, MemoryFact.id < anchor.id),
            )
        )
    items = db.scalars(
        statement.order_by(MemoryFact.recorded_at.desc(), MemoryFact.id.desc()).limit(limit + 1)
    ).all()
    more, items = len(items) > limit, items[:limit]
    return {
        "items": [memory_data(item) for item in items],
        "next_cursor": items[-1].id if more else None,
    }


@router.get("/memories/{memory_id}/sources", response_model=SourcePage)
def get_sources(
    memory_id: str,
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(30, ge=1, le=100),
    before_id: str | None = None,
):
    owned_memory(db, user.id, memory_id)
    statement = (
        select(MemorySource, Message)
        .join(
            Message,
            and_(Message.user_id == MemorySource.user_id, Message.id == MemorySource.message_id),
        )
        .where(MemorySource.memory_id == memory_id, MemorySource.user_id == user.id)
    )
    if before_id:
        anchor = db.scalar(
            select(MemorySource).where(
                MemorySource.id == before_id,
                MemorySource.user_id == user.id,
                MemorySource.memory_id == memory_id,
            )
        )
        if anchor is None:
            raise ApiError(404, "NOT_FOUND", "来源位置不存在或无法访问")
        statement = statement.where(
            or_(
                MemorySource.created_at < anchor.created_at,
                and_(MemorySource.created_at == anchor.created_at, MemorySource.id < anchor.id),
            )
        )
    rows = db.execute(
        statement.order_by(MemorySource.created_at.desc(), MemorySource.id.desc()).limit(limit + 1)
    ).all()
    more, rows = len(rows) > limit, rows[:limit]
    return {
        "items": [
            {
                "id": source.id,
                "source_excerpt": source.source_excerpt,
                "conversation_id": message.conversation_id,
                "message": message_data(message),
            }
            for source, message in rows
        ],
        "next_cursor": rows[-1][0].id if more else None,
    }
