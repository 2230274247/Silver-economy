"""T11B additive place consent/selections and bounded map query receipts."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t11b_maps"
down_revision = "t11a_draft"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "task_drafts",
        sa.Column("location_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for name in ("origin_place", "destination_place", "map_snapshot"):
        op.add_column("task_drafts", sa.Column(name, sa.JSON(), nullable=True))
    op.create_table(
        "map_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("client_request_id", sa.String(36), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(48)),
        sa.Column("result", sa.JSON()),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("expires_at", DATETIME(fsp=6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.UniqueConstraint("user_id", "client_request_id", "operation"),
        sa.ForeignKeyConstraint(["user_id", "draft_id"], ["task_drafts.user_id", "task_drafts.id"]),
    )
    op.create_index("ix_map_requests_user_id", "map_requests", ["user_id"])
    op.create_index(
        "ix_map_requests_cache",
        "map_requests",
        ["user_id", "draft_id", "operation", "fingerprint", "created_at"],
    )
    op.create_table(
        "map_budget",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("map_budget")
    op.drop_table("map_requests")
    for name in ("map_snapshot", "destination_place", "origin_place", "location_consent"):
        op.drop_column("task_drafts", name)
