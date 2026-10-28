"""T11E terminal departure state and audited-task schema repair."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t11e_trip_details"
down_revision = "t11d_devices"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("outing_tasks", sa.Column("departed_at", DATETIME(fsp=6), nullable=True))
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("task_audit_logs")
    has_user_foreign_key = any(
        foreign_key.get("referred_table") == "users"
        and foreign_key.get("constrained_columns") == ["user_id"]
        for foreign_key in foreign_keys
    )
    if not has_user_foreign_key:
        op.create_foreign_key(
            "fk_task_audit_logs_user_id_users",
            "task_audit_logs",
            "users",
            ["user_id"],
            ["id"],
        )


def downgrade():
    op.drop_column("outing_tasks", "departed_at")
