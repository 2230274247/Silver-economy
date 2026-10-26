import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError
from app.core.security import CurrentUser, DatabaseSession, utc_now
from app.models.entities import Conversation, Message
from app.schemas.chat import ConversationOut, ConversationPage, MessagePage, SendResult
from app.services.model_chat import generate_reply

router = APIRouter(prefix="/api/v1")


def timestamp(value: datetime | None):
    return value.replace(tzinfo=UTC).isoformat() if value else None


def conversation_data(item: Conversation):
    return {
        "id": item.id,
        "title": item.title,
        "created_at": timestamp(item.created_at),
        "last_message_at": timestamp(item.last_message_at),
    }


def message_data(item: Message):
    return {
        "id": item.id,
        "role": item.role,
        "content": item.content,
        "status": item.status,
        "error_code": item.error_code,
        "created_at": timestamp(item.created_at),
        "reply_to_message_id": item.reply_to_message_id,
        "client_request_id": item.client_request_id,
        "provider": item.provider,
        "memory_status": item.memory_status,
    }


def owned_conversation(db, user_id, conversation_id, *, lock=False):
    statement = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    )
    if lock:
        statement = statement.with_for_update()
    item = db.scalar(statement)
    if item is None:
        raise ApiError(404, "NOT_FOUND", "会话不存在或无法访问")
    return item


@router.post("/conversations", status_code=201, response_model=ConversationOut)
def create_conversation(user: CurrentUser, db: DatabaseSession):
    item = Conversation(user_id=user.id, created_at=utc_now())
    db.add(item)
    db.commit()
    return conversation_data(item)


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(30, ge=1, le=100),
    before_id: str | None = None,
):
    statement = select(Conversation).where(Conversation.user_id == user.id)
    if before_id:
        anchor = owned_conversation(db, user.id, before_id)
        statement = statement.where(
            or_(
                Conversation.created_at < anchor.created_at,
                and_(Conversation.created_at == anchor.created_at, Conversation.id < anchor.id),
            )
        )
    items = db.scalars(
        statement.order_by(Conversation.created_at.desc(), Conversation.id.desc()).limit(limit + 1)
    ).all()
    more = len(items) > limit
    items = items[:limit]
    return {
        "items": [conversation_data(item) for item in items],
        "next_cursor": items[-1].id if more else None,
    }


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: str, user: CurrentUser, db: DatabaseSession):
    return conversation_data(owned_conversation(db, user.id, conversation_id))


@router.get("/conversations/{conversation_id}/messages", response_model=MessagePage)
def list_messages(
    conversation_id: str,
    user: CurrentUser,
    db: DatabaseSession,
    limit: int = Query(30, ge=1, le=100),
    before_id: str | None = None,
):
    owned_conversation(db, user.id, conversation_id)
    statement = select(Message).where(
        Message.user_id == user.id, Message.conversation_id == conversation_id
    )
    if before_id:
        anchor = db.scalar(statement.where(Message.id == before_id))
        if anchor is None:
            raise ApiError(404, "NOT_FOUND", "无法读取该历史位置")
        statement = statement.where(
            or_(
                Message.created_at < anchor.created_at,
                and_(Message.created_at == anchor.created_at, Message.id < anchor.id),
            )
        )
    items = db.scalars(
        statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
    ).all()
    more = len(items) > limit
    items = items[:limit]
    return {
        "items": [message_data(item) for item in reversed(items)],
        "next_cursor": items[-1].id if more else None,
    }


class SendMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=2000)
    client_request_id: uuid.UUID

    @field_validator("content")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Message must contain text")
        return value


def saved_result(db, user_message, *, replayed=False):
    assistant = db.scalar(
        select(Message).where(
            Message.user_id == user_message.user_id, Message.reply_to_message_id == user_message.id
        )
    )
    return {
        "user_message": message_data(user_message),
        "assistant_message": message_data(assistant),
        "replayed": replayed,
        "provider": assistant.provider or "not_configured",
    }


def retry_if_not_called(db, item):
    assistant = db.scalar(
        select(Message).where(
            Message.user_id == item.user_id,
            Message.reply_to_message_id == item.id,
        )
    )
    if assistant.error_code in {"MODEL_NOT_CONFIGURED", "MODEL_BUDGET_EXCEEDED"}:
        assistant.status, assistant.error_code = "pending", None
        generate_reply(db, item, assistant)


@router.post("/conversations/{conversation_id}/messages", response_model=SendResult)
def send_message(
    conversation_id: str, payload: SendMessage, user: CurrentUser, db: DatabaseSession
):
    conversation = owned_conversation(db, user.id, conversation_id, lock=True)
    request_id = str(payload.client_request_id)
    existing = db.scalar(
        select(Message).where(Message.user_id == user.id, Message.client_request_id == request_id)
    )
    if existing:
        if existing.conversation_id != conversation_id or existing.content != payload.content:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "同一发送编号对应的内容不同，请勿重复提交")
        retry_if_not_called(db, existing)
        return saved_result(db, existing, replayed=True)
    now = utc_now()
    if conversation.last_message_at and now <= conversation.last_message_at:
        now = conversation.last_message_at + timedelta(microseconds=1)
    item = Message(
        user_id=user.id,
        conversation_id=conversation_id,
        role="user",
        content=payload.content,
        client_request_id=request_id,
        created_at=now,
        status="saved",
    )
    try:
        db.add(item)
        db.flush()
        assistant = Message(
            user_id=user.id,
            conversation_id=conversation_id,
            role="assistant",
            content="",
            reply_to_message_id=item.id,
            status="pending",
            created_at=now + timedelta(microseconds=1),
        )
        db.add(assistant)
        conversation.last_message_at = assistant.created_at
        if conversation.title == "新对话":
            conversation.title = payload.content.strip()[:24]
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Message).where(
                Message.user_id == user.id, Message.client_request_id == request_id
            )
        )
        if (
            existing
            and existing.conversation_id == conversation_id
            and existing.content == payload.content
        ):
            return saved_result(db, existing, replayed=True)
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "发送编号冲突，请重新确认后发送") from None
    generate_reply(db, item, assistant)
    return saved_result(db, item)
