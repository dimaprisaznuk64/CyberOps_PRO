from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

CHANNEL_VALUES = ("web", "email", "telegram")


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    scan_id: int | None = None
    title: str
    body: str | None = None
    severity: str | None = None
    is_read: bool
    created_at: datetime
    channel: str = "web"
    destination: str | None = None
    status: str = "sent"
    sent_at: datetime | None = None
    error: str | None = None


class NotificationReadUpdate(BaseModel):
    is_read: bool = True


class NotificationPreferencesOut(BaseModel):
    """Що канал увімкнено на сервері + власні налаштування користувача."""

    email_available: bool
    telegram_available: bool
    server_min_severity: str
    effective_min_severity: str
    email: str | None = None
    telegram_chat_id: str | None = None
    notify_email: bool = True
    notify_telegram: bool = True
    notify_min_severity: str = "high"


class NotificationPreferencesUpdate(BaseModel):
    email: EmailStr | None = None
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    notify_email: bool | None = None
    notify_telegram: bool | None = None
    notify_min_severity: str | None = None


class NotificationTestRequest(BaseModel):
    channel: str = Field(default="email", pattern="^(email|telegram)$")
