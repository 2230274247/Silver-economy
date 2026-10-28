"""T11A additive owned task drafts; no scheduled jobs or changes to old tables."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t11a_draft"
down_revision = "t09_update"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("source_message_id", sa.String(36), nullable=False),
        sa.Column("last_message_id", sa.String(36), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("date_text", sa.String(80), nullable=False),
        sa.Column("clock_text", sa.String(80), nullable=False),
        sa.Column("period_text", sa.String(16), nullable=False),
        sa.Column("time_reference_at", DATETIME(fsp=6), nullable=False),
        sa.Column("target_at", DATETIME(fsp=6), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("time_semantics", sa.String(16), nullable=False),
        sa.Column("origin", sa.String(200), nullable=False),
        sa.Column("destination", sa.String(200), nullable=False),
        sa.Column("transport", sa.String(16), nullable=False),
        sa.Column("lead_minutes", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", DATETIME(fsp=6), nullable=True),
        sa.Column("extractor_provider", sa.String(32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("user_id", "id"),
        sa.UniqueConstraint("user_id", "source_message_id", "ordinal"),
        sa.ForeignKeyConstraint(
            ["user_id", "conversation_id"], ["conversations.user_id", "conversations.id"]
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "source_message_id"],
            ["messages.user_id", "messages.id"],
            name="fk_task_drafts_source_message",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "last_message_id"],
            ["messages.user_id", "messages.id"],
            name="fk_task_drafts_last_message",
        ),
    )
    op.create_index("ix_task_drafts_user_id", "task_drafts", ["user_id"])
    op.create_index(
        "ix_task_drafts_conversation",
        "task_drafts",
        ["user_id", "conversation_id", "created_at", "id"],
    )


def downgrade():
    op.drop_table("task_drafts")
