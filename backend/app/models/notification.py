from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CHANNEL_WEB = "web"
CHANNEL_EMAIL = "email"
CHANNEL_TELEGRAM = "telegram"
CHANNELS = (CHANNEL_WEB, CHANNEL_EMAIL, CHANNEL_TELEGRAM)
EXTERNAL_CHANNELS = (CHANNEL_EMAIL, CHANNEL_TELEGRAM)

STATUS_SENT = "sent"
STATUS_PENDING = "pending"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
DELIVERY_STATUSES = (STATUS_SENT, STATUS_PENDING, STATUS_FAILED, STATUS_SKIPPED)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_id: Mapped[int | None] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Канал доставки: web — запис у БД (+WebSocket), email/telegram — зовнішні
    channel: Mapped[str] = mapped_column(
        String(20), default=CHANNEL_WEB, server_default=CHANNEL_WEB, nullable=False, index=True
    )
    # Адреса призначення для зовнішніх каналів (email або telegram chat id)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=STATUS_SENT, server_default=STATUS_SENT, nullable=False, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
