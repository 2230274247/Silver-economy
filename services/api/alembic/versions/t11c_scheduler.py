"""T11C deterministic schedule, owned reminder outbox and audited lifecycle.

The migration is additive: existing drafts, messages and memories remain intact.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t11c_scheduler"
down_revision = "t11b_maps"
branch_labels = None
depends_on = None


def upgrade():
    for name, default in (("access_buffer_minutes", "10"), ("contingency_buffer_minutes", "15")):
        op.add_column(
            "task_drafts",
            sa.Column(name, sa.Integer(), nullable=False, server_default=sa.text(default)),
        )
    op.add_column("task_drafts", sa.Column("schedule_preview", sa.JSON(), nullable=True))
    op.add_column("task_drafts", sa.Column("scheduled_task_id", sa.String(36), nullable=True))

    op.create_table(
        "outing_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("source_message_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("time_semantics", sa.String(16), nullable=False),
        sa.Column("target_at", DATETIME(fsp=6), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("origin", sa.String(200), nullable=False),
        sa.Column("destination", sa.String(200), nullable=False),
        sa.Column("transport", sa.String(16), nullable=False),
        sa.Column("route_snapshot", sa.JSON(), nullable=True),
        sa.Column("weather_snapshot", sa.JSON(), nullable=True),
        sa.Column("calculation_basis", sa.JSON(), nullable=False),
        sa.Column("departure_at", DATETIME(fsp=6), nullable=False),
        sa.Column("reminder_at", DATETIME(fsp=6), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False),
        sa.Column("preview_id", sa.String(36), nullable=False),
        sa.Column("confirmed_at", DATETIME(fsp=6), nullable=False),
        sa.Column("cancelled_at", DATETIME(fsp=6), nullable=True),
        sa.Column("completed_at", DATETIME(fsp=6), nullable=True),
        sa.UniqueConstraint("user_id", "id"),
        sa.UniqueConstraint("user_id", "draft_id"),
        sa.UniqueConstraint("user_id", "idempotency_key"),
        sa.ForeignKeyConstraint(["user_id", "draft_id"], ["task_drafts.user_id", "task_drafts.id"]),
        sa.ForeignKeyConstraint(
            ["user_id", "source_message_id"], ["messages.user_id", "messages.id"]
        ),
    )
    op.create_index("ix_outing_tasks_user_id", "outing_tasks", ["user_id"])
    op.create_index(
        "ix_outing_tasks_user_status_time",
        "outing_tasks",
        ["user_id", "status", "reminder_at"],
    )

    op.add_column("reminders", sa.Column("outing_task_id", sa.String(36), nullable=True))
    op.add_column(
        "reminders",
        sa.Column("task_revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_foreign_key(
        "fk_reminders_outing_task",
        "reminders",
        "outing_tasks",
        ["user_id", "outing_task_id"],
        ["user_id", "id"],
    )

    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outing_task_id", sa.String(36), nullable=False),
        sa.Column("reminder_id", sa.String(36), nullable=False),
        sa.Column("task_revision", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(24), nullable=False),
        sa.Column("scheduled_at", DATETIME(fsp=6), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", DATETIME(fsp=6), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("lease_owner", sa.String(120), nullable=True),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", DATETIME(fsp=6), nullable=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("provider_message_id", sa.String(120), nullable=True),
        sa.Column("last_attempt_at", DATETIME(fsp=6), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("completed_at", DATETIME(fsp=6), nullable=True),
        sa.UniqueConstraint("user_id", "id"),
        sa.UniqueConstraint("user_id", "idempotency_key"),
        sa.ForeignKeyConstraint(
            ["user_id", "outing_task_id"], ["outing_tasks.user_id", "outing_tasks.id"]
        ),
        sa.ForeignKeyConstraint(["user_id", "reminder_id"], ["reminders.user_id", "reminders.id"]),
    )
    op.create_index("ix_notification_jobs_user_id", "notification_jobs", ["user_id"])
    op.create_index(
        "ix_notification_jobs_due",
        "notification_jobs",
        ["status", "scheduled_at", "next_attempt_at"],
    )

    op.create_table(
        "task_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("outing_task_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("actor", sa.String(24), nullable=False),
        sa.Column("task_revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["user_id", "outing_task_id"], ["outing_tasks.user_id", "outing_tasks.id"]
        ),
    )
    op.create_index("ix_task_audit_logs_user_id", "task_audit_logs", ["user_id"])
    op.create_index(
        "ix_task_audit_task_created",
        "task_audit_logs",
        ["outing_task_id", "created_at", "id"],
    )


def downgrade():
    op.drop_table("task_audit_logs")
    op.drop_table("notification_jobs")
    op.drop_constraint("fk_reminders_outing_task", "reminders", type_="foreignkey")
    op.drop_column("reminders", "task_revision")
    op.drop_column("reminders", "outing_task_id")
    op.drop_table("outing_tasks")
    op.drop_column("task_drafts", "scheduled_task_id")
    op.drop_column("task_drafts", "schedule_preview")
    op.drop_column("task_drafts", "contingency_buffer_minutes")
    op.drop_column("task_drafts", "access_buffer_minutes")
