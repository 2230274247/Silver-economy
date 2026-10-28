"""T13 opt-out proactive route and weather refresh policy."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t13_proactive_updates"
down_revision = "t11e_trip_details"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "outing_tasks",
        sa.Column(
            "proactive_updates_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "outing_tasks",
        sa.Column(
            "proactive_change_threshold_minutes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
    )
    op.add_column(
        "outing_tasks",
        sa.Column("proactive_refresh_at", DATETIME(fsp=6), nullable=True),
    )
    op.add_column(
        "outing_tasks",
        sa.Column("last_proactive_refresh_at", DATETIME(fsp=6), nullable=True),
    )


def downgrade():
    op.drop_column("outing_tasks", "last_proactive_refresh_at")
    op.drop_column("outing_tasks", "proactive_refresh_at")
    op.drop_column("outing_tasks", "proactive_change_threshold_minutes")
    op.drop_column("outing_tasks", "proactive_updates_enabled")
