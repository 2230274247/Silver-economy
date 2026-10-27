from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.tasks import TaskDraftOut


class MemoryReferenceOut(BaseModel):
    label: str
    memory_id: str
    source_message_id: str
    conversation_id: str
    source_excerpt: str
    recorded_at: datetime
    status: str
    confirmed: bool
    is_synthetic: bool
    extractor_provider: str | None
    evidence_text: str
    evidence_origin: str
    memory_revision: int
    changed_since_reply: bool


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    last_message_at: datetime | None


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    status: str
    error_code: str | None
    created_at: datetime
    reply_to_message_id: str | None
    client_request_id: str | None
    provider: str | None
    memory_status: str | None
    memory_refs: list[MemoryReferenceOut] = Field(default_factory=list)
    task_drafts: list[TaskDraftOut] = Field(default_factory=list)


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    next_cursor: str | None


class MessagePage(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None


class SendResult(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    replayed: bool
    provider: str
