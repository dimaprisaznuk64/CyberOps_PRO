from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.models.notification import (
    CHANNEL_EMAIL,
    CHANNEL_TELEGRAM,
    CHANNELS,
    STATUS_PENDING,
    Notification,
)
from app.models.user import NOTIFY_SEVERITIES, User
from app.schemas.notification import (
    NotificationOut,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
    NotificationReadUpdate,
    NotificationTestRequest,
)
from app.services import notifications as notify_service
from app.tasks import get_notification_enqueuer

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _preferences_payload(user: User) -> NotificationPreferencesOut:
    status_map = notify_service.channel_status()
    prefs = notify_service.prefs_from_user(user)
    return NotificationPreferencesOut(
        email_available=status_map[CHANNEL_EMAIL],
        telegram_available=status_map[CHANNEL_TELEGRAM],
        server_min_severity=notify_service.normalize_severity(settings.notify_min_severity)
        or "high",
        effective_min_severity=notify_service.effective_threshold(prefs.notify_min_severity),
        email=user.email,
        telegram_chat_id=user.telegram_chat_id,
        notify_email=user.notify_email,
        notify_telegram=user.notify_telegram,
        notify_min_severity=user.notify_min_severity,
    )


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    channel: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if channel is not None and channel not in CHANNELS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Невідомий канал")
    query = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    if channel is not None:
        query = query.where(Notification.channel == channel)
    result = await session.scalars(query)
    return list(result.all())


@router.get("/preferences", response_model=NotificationPreferencesOut)
async def get_preferences(user: User = Depends(get_current_user)):
    return _preferences_payload(user)


@router.patch("/preferences", response_model=NotificationPreferencesOut)
async def update_preferences(
    payload: NotificationPreferencesUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data = payload.model_dump(exclude_unset=True)
    severity = data.get("notify_min_severity")
    if severity is not None and severity not in NOTIFY_SEVERITIES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Невалідний рівень важливості")

    new_email = data.get("email")
    if new_email:
        taken = await session.scalar(
            select(User.id).where(User.email == new_email, User.id != user.id)
        )
        if taken is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email уже зайнятий")

    for key, value in data.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return _preferences_payload(user)


@router.post("/test", response_model=NotificationOut, status_code=status.HTTP_202_ACCEPTED)
async def send_test_notification(
    payload: NotificationTestRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    enqueue: Callable[[int], None] = Depends(get_notification_enqueuer),
):
    """Створює тестове сповіщення в обраному каналі й віддає його в Celery."""
    if not notify_service.channel_available(payload.channel):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Канал {payload.channel} вимкнено на сервері"
        )
    prefs = notify_service.prefs_from_user(user)
    if payload.channel == CHANNEL_EMAIL and not (prefs.email or "").strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Спершу вкажіть email у налаштуваннях"
        )
    chat_id = (prefs.telegram_chat_id or "").strip()
    if payload.channel == CHANNEL_TELEGRAM and not chat_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Спершу вкажіть Telegram chat id у налаштуваннях"
        )

    notification = Notification(
        user_id=user.id,
        scan_id=None,
        title="Тестове сповіщення CyberOps PRO",
        body="Якщо ви це читаєте — канал налаштовано правильно.",
        severity="info",
        channel=payload.channel,
        destination=prefs.email if payload.channel == CHANNEL_EMAIL else chat_id,
        status=STATUS_PENDING,
        is_read=True,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    enqueue(notification.id)
    return notification


@router.post("/{notification_id}/retry", response_model=NotificationOut)
async def retry_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    enqueue: Callable[[int], None] = Depends(get_notification_enqueuer),
):
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сповіщення не знайдено")
    if notification.channel not in (CHANNEL_EMAIL, CHANNEL_TELEGRAM):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Повторна доставка доступна лише для email/telegram"
        )
    notification.status = STATUS_PENDING
    notification.error = None
    await session.commit()
    await session.refresh(notification)
    enqueue(notification.id)
    return notification


@router.get("/{notification_id}", response_model=NotificationOut)
async def get_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сповіщення не знайдено")
    return notification


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: int,
    payload: NotificationReadUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сповіщення не знайдено")
    notification.is_read = payload.is_read
    await session.commit()
    await session.refresh(notification)
    return notification


@router.post("/read-all", response_model=int)
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await session.commit()
    return result.rowcount or 0
