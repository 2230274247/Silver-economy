"""Add operator role, independent budget and durable web evidence."""

import sqlalchemy as sa

from alembic import op

revision = "t14_chat_assistant"
down_revision = "t13_proactive_updates"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0"))
    )
    op.add_column("messages", sa.Column("search_context", sa.JSON(), nullable=True))
    op.create_table(
        "admin_model_budget",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("admin_model_budget")
    op.drop_column("messages", "search_context")
    op.drop_column("users", "is_admin")
