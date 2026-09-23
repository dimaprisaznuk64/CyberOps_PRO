"""assets (колишні targets), renamed FKs

Revision ID: 0005_assets
Revises: 0004_audit_notifications_reports
Create Date: 2026-09-23

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_assets"
down_revision: Union[str, None] = "0004_audit_notifications_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("targets", "assets")

    with op.batch_alter_table("scans") as batch_op:
        batch_op.alter_column("target_id", new_column_name="asset_id")

    with op.batch_alter_table("reports") as batch_op:
        batch_op.alter_column("target_id", new_column_name="asset_id")

    op.add_column(
        "assets",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="ip"),
    )
    op.add_column(
        "assets",
        sa.Column("docker_container", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assets", "docker_container")
    op.drop_column("assets", "kind")

    with op.batch_alter_table("reports") as batch_op:
        batch_op.alter_column("asset_id", new_column_name="target_id")

    with op.batch_alter_table("scans") as batch_op:
        batch_op.alter_column("asset_id", new_column_name="target_id")

    op.rename_table("assets", "targets")