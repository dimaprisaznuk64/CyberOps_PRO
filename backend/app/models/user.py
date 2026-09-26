from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_ANALYST, ROLE_USER)

NOTIFY_SEVERITIES = ("info", "low", "medium", "high", "critical")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=ROLE_USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Налаштування сповіщень (канали email/telegram) ---
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_telegram: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_min_severity: Mapped[str] = mapped_column(
        String(20), default="high", server_default="high", nullable=False
    )

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_analyst(self) -> bool:
        return self.role in (ROLE_ANALYST, ROLE_ADMIN)
