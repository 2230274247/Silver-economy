from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
