"""notification channels (email/telegram) + per-user preferences

Revision ID: 0006_notification_channels
Revises: 0005_assets
Create Date: 2026-09-26

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_notification_channels"
down_revision: Union[str, None] = "0005_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(
            sa.Column(
                "channel", sa.String(length=20), nullable=False, server_default="web"
            )
        )
        batch_op.add_column(sa.Column("destination", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status", sa.String(length=20), nullable=False, server_default="sent"
            )
        )
        batch_op.add_column(
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("error", sa.String(length=500), nullable=True))
    op.create_index("ix_notifications_channel", "notifications", ["channel"])
    op.create_index("ix_notifications_status", "notifications", ["status"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("telegram_chat_id", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "notify_email", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )
        batch_op.add_column(
            sa.Column(
                "notify_telegram", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )
        batch_op.add_column(
            sa.Column(
                "notify_min_severity",
                sa.String(length=20),
                nullable=False,
                server_default="high",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("notify_min_severity")
        batch_op.drop_column("notify_telegram")
        batch_op.drop_column("notify_email")
        batch_op.drop_column("telegram_chat_id")

    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_channel", table_name="notifications")
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_column("error")
        batch_op.drop_column("sent_at")
        batch_op.drop_column("status")
        batch_op.drop_column("destination")
        batch_op.drop_column("channel")
