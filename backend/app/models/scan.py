from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

SCAN_PENDING = "pending"
SCAN_RUNNING = "running"
SCAN_DONE = "done"
SCAN_FAILED = "failed"
SCAN_STATUSES = (SCAN_PENDING, SCAN_RUNNING, SCAN_DONE, SCAN_FAILED)

SCAN_TYPE_PING = "ping"
SCAN_TYPE_TCP = "tcp"
SCAN_TYPE_QUICK = "quick"
SCAN_TYPES = (SCAN_TYPE_PING, SCAN_TYPE_TCP, SCAN_TYPE_QUICK)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=SCAN_PENDING, nullable=False, index=True
    )
    scan_type: Mapped[str] = mapped_column(String(20), default=SCAN_TYPE_TCP, nullable=False)
    ports: Mapped[str | None] = mapped_column(String(255), nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    target = relationship("Target", back_populates="scans")
