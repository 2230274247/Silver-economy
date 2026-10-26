"""T09 non-destructive memory control and revision evidence."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t09_update"
down_revision = "t08_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "memory_facts", sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "memory_facts",
        sa.Column("value_origin", sa.String(24), nullable=False, server_default="chat"),
    )
    op.add_column(
        "memory_uses",
        sa.Column("memory_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "memory_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("memory_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor", sa.String(24), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "memory_id"], ["memory_facts.user_id", "memory_facts.id"]
        ),
        sa.UniqueConstraint("memory_id", "revision"),
    )
    op.create_index("ix_memory_revisions_user_id", "memory_revisions", ["user_id"])
    # Backfill defaults above, then match ORM application defaults (no server defaults).
    op.alter_column("memory_facts", "revision", existing_type=sa.Integer(), server_default=None)
    op.alter_column(
        "memory_facts", "value_origin", existing_type=sa.String(24), server_default=None
    )
    op.alter_column(
        "memory_uses", "memory_revision", existing_type=sa.Integer(), server_default=None
    )


def downgrade():
    op.drop_table("memory_revisions")
    op.drop_column("memory_uses", "memory_revision")
    op.drop_column("memory_facts", "value_origin")
    op.drop_column("memory_facts", "revision")
