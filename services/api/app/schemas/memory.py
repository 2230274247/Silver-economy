from datetime import datetime

from pydantic import BaseModel

from app.schemas.chat import MessageOut


class MemoryOut(BaseModel):
    id: str
    kind: str
    key: str
    value: str
    status: str
    event_at: datetime | None
    event_precision: str
    time_expression: str | None
    recorded_at: datetime
    confirmed_at: datetime | None
    retrieval_allowed: bool
    extractor_provider: str | None
    extractor_version: str | None
    is_synthetic: bool


class MemoryPage(BaseModel):
    items: list[MemoryOut]
    next_cursor: str | None


class SourceOut(BaseModel):
    id: str
    source_excerpt: str
    conversation_id: str
    message: MessageOut


class SourcePage(BaseModel):
    items: list[SourceOut]
    next_cursor: str | None
