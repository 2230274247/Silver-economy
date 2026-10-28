from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    revision: int
    value_origin: str


class MemoryPage(BaseModel):
    items: list[MemoryOut]
    next_cursor: str | None


class TimelineItem(MemoryOut):
    event_label: str
    source_count: int


class TimelinePage(BaseModel):
    items: list[TimelineItem]
    next_cursor: str | None


class SourceOut(BaseModel):
    id: str
    source_excerpt: str
    conversation_id: str
    message: MessageOut


class SourcePage(BaseModel):
    items: list[SourceOut]
    next_cursor: str | None


class MemoryMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


class MemoryConfirmation(MemoryMutation):
    confirmed: bool


class MemoryPermission(MemoryMutation):
    allowed: bool


class MemoryCorrection(MemoryMutation):
    kind: Literal[
        "health", "relationship", "work", "habit", "interest", "travel", "date", "event", "place"
    ]
    key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=1000)
    time_expression: str = Field(default="", max_length=120)

    @field_validator("key", "value", "time_expression")
    @classmethod
    def valid_text(cls, value, info):
        value.encode("utf-8")
        if info.field_name != "time_expression" and not value.strip():
            raise ValueError("Cannot be blank")
        return value


class RevisionOut(BaseModel):
    revision: int
    action: str
    actor: str
    created_at: datetime
    before: dict
    after: dict


class RevisionPage(BaseModel):
    items: list[RevisionOut]
    next_revision: int | None
