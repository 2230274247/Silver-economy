from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.memory.context import MemoryAnswerEnvelope

Transport = Literal["unknown", "taxi", "driving", "transit", "walking", "cycling"]
TimeSemantics = Literal["unknown", "arrival", "departure", "at"]


class TaskCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str = Field(default="", max_length=36)
    kind: Literal["outing", "reminder"] = "outing"
    source_excerpt: str = Field(min_length=1, max_length=2000)
    date_text: str = Field(default="", max_length=80)
    clock_text: str = Field(default="", max_length=80)
    period_text: str = Field(default="", max_length=16)
    origin: str = Field(default="", max_length=200)
    destination: str = Field(default="", max_length=200)
    transport: Transport = "unknown"
    time_semantics: TimeSemantics = "unknown"


class TaskEnvelope(MemoryAnswerEnvelope):
    outings: list[TaskCandidate] = Field(default_factory=list, max_length=3)


class TaskDraftPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    time_text: str = Field(max_length=160)
    time_semantics: TimeSemantics
    origin: str = Field(max_length=200)
    destination: str = Field(max_length=200)
    transport: Transport
    lead_minutes: int = Field(ge=0, le=10080)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()


class TaskDraftAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    action: Literal["confirm", "defer"]


class TaskDraftOut(BaseModel):
    id: str
    conversation_id: str
    source_message_id: str
    last_message_id: str
    source_excerpt: str
    kind: str
    title: str
    status: str
    revision: int
    target_at: datetime | None
    date_text: str
    clock_text: str
    period_text: str
    timezone: str
    time_reference_at: datetime
    resolved_date: str | None
    time_semantics: str
    origin: str
    destination: str
    transport: str
    lead_minutes: int
    missing_fields: list[str]
    evidence: dict
    confirmed_at: datetime | None
    extractor_provider: str
    is_synthetic: bool
    location_consent: bool = False
    origin_place: dict | None = None
    destination_place: dict | None = None
    map_snapshot: dict | None = None
    scheduling_status: Literal["not_scheduled"] = "not_scheduled"


class TaskDraftPage(BaseModel):
    items: list[TaskDraftOut]
