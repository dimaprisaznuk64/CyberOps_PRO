"""compressed raw nmap archive for scans

Revision ID: 0007_scan_raw_archive
Revises: 0006_notification_channels
Create Date: 2026-09-28

Сирий nmap XML — найбільший payload у базі: -sV з NSE-скриптами навіть для
одного хоста дає сотні кілобайт, а на /24 — мегабайти. Тому архів зберігається
стиснутим (raw_xml_gz), а стара колонка raw_xml залишається: неї не переносимо
вниз, щоб rollback не втратив дані, а читання з неї лишається сумісним
(app/services/raw_nmap.py).

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_scan_raw_archive"
down_revision: str | None = "0006_notification_channels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("scans") as batch_op:
        batch_op.add_column(sa.Column("raw_xml_gz", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scans") as batch_op:
        batch_op.drop_column("raw_xml_gz")
