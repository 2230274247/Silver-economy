from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UTC_DATETIME, Base, Identity, Updated


class User(Identity, Base):
    __tablename__ = "users"
    login_name: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    disabled_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class Owned:
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)


class AuthSession(Identity, Owned, Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTC_DATETIME, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)


class Conversation(Identity, Owned, Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("user_id", "id"),)
    title: Mapped[str] = mapped_column(String(120), default="新对话")
    last_message_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)


class Message(Identity, Updated, Owned, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "client_request_id"),
        UniqueConstraint("user_id", "reply_to_message_id"),
        ForeignKeyConstraint(
            ["user_id", "conversation_id"], ["conversations.user_id", "conversations.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "reply_to_message_id"], ["messages.user_id", "messages.id"]
        ),
        Index("ix_messages_conversation_created", "conversation_id", "created_at", "id"),
    )
    conversation_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    client_request_id: Mapped[str | None] = mapped_column(String(64))
    reply_to_message_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(24), default="saved")
    error_code: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(32))
    memory_status: Mapped[str | None] = mapped_column(String(32))
    raw_model_output: Mapped[str | None] = mapped_column(Text)


class MemoryFact(Identity, Updated, Owned, Base):
    __tablename__ = "memory_facts"
    __table_args__ = (UniqueConstraint("user_id", "id"), UniqueConstraint("user_id", "fingerprint"))
    kind: Mapped[str] = mapped_column(String(32))
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text)
    fact_status: Mapped[str] = mapped_column(String(24), default="candidate")
    valid_from: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    valid_to: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    event_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    recorded_at: Mapped[datetime] = mapped_column(UTC_DATETIME, server_default=func.now())
    confidence_label: Mapped[str] = mapped_column(String(32), default="explicit")
    deleted_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    time_expression: Mapped[str | None] = mapped_column(String(120))
    event_precision: Mapped[str] = mapped_column(String(24), default="unknown")
    event_timezone: Mapped[str] = mapped_column(String(64), default="Asia/Hong_Kong")
    state_text: Mapped[str | None] = mapped_column(String(80))
    confirmed_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    retrieval_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    extractor_provider: Mapped[str | None] = mapped_column(String(32))
    extractor_version: Mapped[str | None] = mapped_column(String(80))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    value_origin: Mapped[str] = mapped_column(String(24), default="chat")


class MemoryRevision(Identity, Owned, Base):
    __tablename__ = "memory_revisions"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "memory_id"], ["memory_facts.user_id", "memory_facts.id"]),
        UniqueConstraint("memory_id", "revision"),
    )
    memory_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(24))
    before: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)


class MemorySource(Identity, Owned, Base):
    __tablename__ = "memory_sources"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "memory_id"], ["memory_facts.user_id", "memory_facts.id"]),
        ForeignKeyConstraint(["user_id", "message_id"], ["messages.user_id", "messages.id"]),
        UniqueConstraint("memory_id", "message_id"),
    )
    memory_id: Mapped[str] = mapped_column(String(36))
    message_id: Mapped[str] = mapped_column(String(36))
    source_excerpt: Mapped[str] = mapped_column(Text)


class LifeEvent(Identity, Owned, Base):
    __tablename__ = "life_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "source_memory_id"], ["memory_facts.user_id", "memory_facts.id"]
        ),
    )
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    occurred_precision: Mapped[str] = mapped_column(String(24), default="unknown")
    recorded_at: Mapped[datetime] = mapped_column(UTC_DATETIME, server_default=func.now())
    source_memory_id: Mapped[str | None] = mapped_column(String(36))
    is_user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class MemoryUse(Identity, Owned, Base):
    __tablename__ = "memory_uses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "assistant_message_id"], ["messages.user_id", "messages.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "memory_id"],
            ["memory_facts.user_id", "memory_facts.id"],
        ),
        ForeignKeyConstraint(
            ["memory_id", "source_message_id"],
            ["memory_sources.memory_id", "memory_sources.message_id"],
        ),
        UniqueConstraint("assistant_message_id", "memory_id", "source_message_id"),
        UniqueConstraint("assistant_message_id", "reference_label"),
    )
    assistant_message_id: Mapped[str] = mapped_column(String(36))
    memory_id: Mapped[str] = mapped_column(String(36))
    source_message_id: Mapped[str] = mapped_column(String(36))
    reference_label: Mapped[str] = mapped_column(String(8))
    memory_revision: Mapped[int] = mapped_column(Integer, default=1)


class Reminder(Identity, Updated, Owned, Base):
    __tablename__ = "reminders"
    __table_args__ = (UniqueConstraint("user_id", "id"),)
    title: Mapped[str] = mapped_column(String(160))
    due_at: Mapped[datetime] = mapped_column(UTC_DATETIME)
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="pending")


class TaskDraft(Identity, Updated, Owned, Base):
    __tablename__ = "task_drafts"
    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        UniqueConstraint("user_id", "source_message_id", "ordinal"),
        ForeignKeyConstraint(
            ["user_id", "conversation_id"], ["conversations.user_id", "conversations.id"]
        ),
        ForeignKeyConstraint(
            ["user_id", "source_message_id"],
            ["messages.user_id", "messages.id"],
            name="fk_task_drafts_source_message",
        ),
        ForeignKeyConstraint(
            ["user_id", "last_message_id"],
            ["messages.user_id", "messages.id"],
            name="fk_task_drafts_last_message",
        ),
        Index("ix_task_drafts_conversation", "user_id", "conversation_id", "created_at", "id"),
    )
    conversation_id: Mapped[str] = mapped_column(String(36))
    source_message_id: Mapped[str] = mapped_column(String(36))
    last_message_id: Mapped[str] = mapped_column(String(36))
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), default="outing")
    title: Mapped[str] = mapped_column(String(160))
    source_excerpt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    date_text: Mapped[str] = mapped_column(String(80), default="")
    clock_text: Mapped[str] = mapped_column(String(80), default="")
    period_text: Mapped[str] = mapped_column(String(16), default="")
    time_reference_at: Mapped[datetime] = mapped_column(UTC_DATETIME)
    target_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Hong_Kong")
    time_semantics: Mapped[str] = mapped_column(String(16), default="unknown")
    origin: Mapped[str] = mapped_column(String(200), default="")
    destination: Mapped[str] = mapped_column(String(200), default="")
    transport: Mapped[str] = mapped_column(String(16), default="unknown")
    lead_minutes: Mapped[int] = mapped_column(Integer, default=60)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTC_DATETIME)
    extractor_provider: Mapped[str] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    location_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    origin_place: Mapped[dict | None] = mapped_column(JSON)
    destination_place: Mapped[dict | None] = mapped_column(JSON)
    map_snapshot: Mapped[dict | None] = mapped_column(JSON)


class MapRequest(Identity, Owned, Base):
    __tablename__ = "map_requests"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", "operation"),
        ForeignKeyConstraint(["user_id", "draft_id"], ["task_drafts.user_id", "task_drafts.id"]),
        Index(
            "ix_map_requests_cache", "user_id", "draft_id", "operation", "fingerprint", "created_at"
        ),
    )
    draft_id: Mapped[str] = mapped_column(String(36))
    client_request_id: Mapped[str] = mapped_column(String(36))
    operation: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(16))
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    error_code: Mapped[str | None] = mapped_column(String(48))
    result: Mapped[dict | None] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(UTC_DATETIME)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class MapBudget(Base):
    __tablename__ = "map_budget"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)


class ModelUsage(Identity, Owned, Base):
    __tablename__ = "model_usage"
    __table_args__ = (UniqueConstraint("user_id", "request_id", "purpose"),)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    status: Mapped[str] = mapped_column(String(24), default="reserved")
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))


class ModelBudget(Base):
    """Operator account-wide limit, shared by all users and API processes."""

    __tablename__ = "model_budget"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)
