"""T11D encrypted device registrations and outbox device binding."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "t11d_devices"
down_revision = "t11c_scheduler"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", DATETIME(fsp=6), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("push_client_id_ciphertext", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("permission_status", sa.String(24), nullable=False),
        sa.Column("app_version", sa.String(64), nullable=False),
        sa.Column("device_label", sa.String(80), nullable=False),
        sa.Column("last_seen_at", DATETIME(fsp=6), nullable=False),
        sa.Column("revoked_at", DATETIME(fsp=6), nullable=True),
        sa.UniqueConstraint("user_id", "id"),
        sa.UniqueConstraint("user_id", "fingerprint"),
    )
    op.create_index("ix_notification_devices_user_id", "notification_devices", ["user_id"])
    op.create_index(
        "ix_notification_devices_last_seen",
        "notification_devices",
        ["user_id", "revoked_at", "last_seen_at"],
    )
    op.add_column("notification_jobs", sa.Column("device_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_notification_jobs_device",
        "notification_jobs",
        "notification_devices",
        ["user_id", "device_id"],
        ["user_id", "id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_notification_jobs_device",
        "notification_jobs",
        type_="foreignkey",
    )
    op.drop_column("notification_jobs", "device_id")
    op.drop_index("ix_notification_devices_last_seen", table_name="notification_devices")
    op.drop_index("ix_notification_devices_user_id", table_name="notification_devices")
    op.drop_table("notification_devices")
