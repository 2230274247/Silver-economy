from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_, select

from app.api.v1.chat import message_data, timestamp
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import CurrentUser, DatabaseSession
from app.memory.retriever import MemoryRetriever
from app.memory.updater import MemoryUpdater
from app.models.entities import MemoryFact, MemoryRevision, MemorySource, Message, User
from app.schemas.memory import (
    MemoryConfirmation,
    MemoryCorrection,
    MemoryMutation,
    MemoryOut,
    MemoryPage,
    MemoryPermission,
    RevisionPage,
    SourcePage,
)

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
        "revision": item.revision,
        "value_origin": item.value_origin,
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


def mutate(db, user, memory_id, payload, action):
    updater = MemoryUpdater()
    fact = updater.owned_for_update(db, user.id, memory_id, payload.expected_revision)
    updater.apply(db, fact, action, payload)
    db.commit()
    return memory_data(fact)


@router.post("/memories/{memory_id}/confirm", response_model=MemoryOut)
def confirm_memory(
    memory_id: str, payload: MemoryConfirmation, user: CurrentUser, db: DatabaseSession
):
    return mutate(db, user, memory_id, payload, "confirm")


@router.post("/memories/{memory_id}/correct", response_model=MemoryOut)
def correct_memory(
    memory_id: str, payload: MemoryCorrection, user: CurrentUser, db: DatabaseSession
):
    return mutate(db, user, memory_id, payload, "correct")


@router.post("/memories/{memory_id}/invalidate", response_model=MemoryOut)
def invalidate_memory(
    memory_id: str, payload: MemoryMutation, user: CurrentUser, db: DatabaseSession
):
    return mutate(db, user, memory_id, payload, "invalidate")


@router.post("/memories/{memory_id}/permission", response_model=MemoryOut)
def memory_permission(
    memory_id: str, payload: MemoryPermission, user: CurrentUser, db: DatabaseSession
):
    return mutate(db, user, memory_id, payload, "permission")


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str, payload: MemoryMutation, user: CurrentUser, db: DatabaseSession):
    mutate(db, user, memory_id, payload, "delete")
    return {"deleted": True, "raw_messages_retained": True}


@router.get("/memories/{memory_id}/revisions", response_model=RevisionPage)
def memory_revisions(
    memory_id: str,
    user: CurrentUser,
    db: DatabaseSession,
    before_revision: int | None = Query(None, ge=1),
):
    owned_memory(db, user.id, memory_id)
    statement = select(MemoryRevision).where(
        MemoryRevision.user_id == user.id, MemoryRevision.memory_id == memory_id
    )
    if before_revision:
        statement = statement.where(MemoryRevision.revision < before_revision)
    rows = db.scalars(statement.order_by(MemoryRevision.revision.desc()).limit(31)).all()
    return {
        "items": [
            {
                "revision": r.revision,
                "action": r.action,
                "actor": r.actor,
                "created_at": timestamp(r.created_at),
                "before": r.before,
                "after": r.after,
            }
            for r in rows[:30]
        ],
        "next_revision": rows[29].revision if len(rows) > 30 else None,
    }


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


@router.get("/memories/search", response_model=MemoryPage)
def search_memories(
    user: CurrentUser,
    db: DatabaseSession,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(30, ge=1, le=30),
):
    results = MemoryRetriever().retrieve(
        db, user.id, q, provider=get_settings().llm_provider, limit=limit, for_context=False
    )
    return {"items": [memory_data(result.fact) for result in results], "next_cursor": None}


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
