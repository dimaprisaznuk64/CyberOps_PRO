from __future__ import annotations

import asyncio
import html
import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime

import httpx

from app.config import settings
from app.models.notification import (
    CHANNEL_EMAIL,
    CHANNEL_TELEGRAM,
    CHANNEL_WEB,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    STATUS_SKIPPED,
    Notification,
)
from app.services.logging_config import get_logger

logger = get_logger("app.notify")

SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

_SEVERITY_LABEL = {
    "info": "ІНФО",
    "low": "НИЗЬКИЙ",
    "medium": "СЕРЕДНІЙ",
    "high": "ВИСОКИЙ",
    "critical": "КРИТИЧНИЙ",
}

# Повідомлення не довше — телеграм обрізає решту, краще обрізати самі
_TELEGRAM_RESERVE = 120


class DeliveryError(RuntimeError):
    """Помилка доставки зовнішнім каналом (SMTP/Telegram API)."""


@dataclass
class ChannelPrefs:
    email: str | None = None
    telegram_chat_id: str | None = None
    notify_email: bool = True
    notify_telegram: bool = True
    notify_min_severity: str | None = None


@dataclass
class DeliveryResult:
    status: str
    error: str | None = None


def normalize_severity(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized if normalized in SEVERITY_RANK else None


def severity_rank(severity: str | None) -> int:
    return SEVERITY_RANK.get(normalize_severity(severity) or "", -1)


def is_severe_enough(severity: str | None, threshold: str) -> bool:
    return severity_rank(severity) >= severity_rank(threshold)


def effective_threshold(user_threshold: str | None) -> str:
    """Дієвий поріг = найсуворіший із серверного та користувацького.

    Серверний NOTIFY_MIN_SEVERITY — це підлога: користувач може зробити
    поріг суворішим (менше спаму), але не може послабити політику сервера.
    """
    server = normalize_severity(settings.notify_min_severity) or "high"
    user = normalize_severity(user_threshold)
    if user is None:
        return server
    return user if severity_rank(user) > severity_rank(server) else server


def channel_available(channel: str) -> bool:
    if not settings.notifications_enabled:
        return False
    if channel == CHANNEL_EMAIL:
        return bool(settings.smtp_enabled and settings.smtp_host)
    if channel == CHANNEL_TELEGRAM:
        return bool(settings.telegram_enabled and settings.telegram_bot_token)
    return False


def channel_status() -> dict[str, bool]:
    return {
        CHANNEL_WEB: True,
        CHANNEL_EMAIL: channel_available(CHANNEL_EMAIL),
        CHANNEL_TELEGRAM: channel_available(CHANNEL_TELEGRAM),
    }


def prefs_from_user(user: object) -> ChannelPrefs:
    return ChannelPrefs(
        email=getattr(user, "email", None),
        telegram_chat_id=getattr(user, "telegram_chat_id", None),
        notify_email=bool(getattr(user, "notify_email", True)),
        notify_telegram=bool(getattr(user, "notify_telegram", True)),
        notify_min_severity=getattr(user, "notify_min_severity", None),
    )


def resolve_channels(severity: str | None, prefs: ChannelPrefs) -> list[tuple[str, str]]:
    """Які зовнішні канали підходять для сповіщення з таким severity.

    Повертає список пар (channel, destination) у стабільному порядку.
    Канал не розглядається, якщо вимкнений на сервері, вимкнений у користувача
    або немає адреси призначення.
    """
    if not is_severe_enough(severity, effective_threshold(prefs.notify_min_severity)):
        return []

    plan: list[tuple[str, str]] = []
    email = (prefs.email or "").strip()
    if prefs.notify_email and email and channel_available(CHANNEL_EMAIL):
        plan.append((CHANNEL_EMAIL, email))
    chat_id = (prefs.telegram_chat_id or settings.telegram_chat_id or "").strip()
    if prefs.notify_telegram and chat_id and channel_available(CHANNEL_TELEGRAM):
        plan.append((CHANNEL_TELEGRAM, chat_id))
    return plan


def build_notifications(
    *,
    user_id: int,
    scan_id: int | None,
    title: str,
    body: str | None,
    severity: str | None,
    prefs: ChannelPrefs,
) -> list[Notification]:
    """Створює рядки notifications: завжди web + зовнішні канали за порогом.

    Зовнішні рядки одразу pending — їх доставить окремий Celery-таск, щоб
    SMTP/Telegram не блокували worker.
    """
    notifications = [
        Notification(
            user_id=user_id,
            scan_id=scan_id,
            title=title,
            body=body,
            severity=severity,
            channel=CHANNEL_WEB,
            status=STATUS_SENT,
        )
    ]
    for channel, destination in resolve_channels(severity, prefs):
        notifications.append(
            Notification(
                user_id=user_id,
                scan_id=scan_id,
                title=title,
                body=body,
                severity=severity,
                channel=channel,
                destination=destination,
                status=STATUS_PENDING,
            )
        )
    return notifications


def _scan_link(scan_id: int | None) -> str:
    if not scan_id:
        return ""
    return f"{settings.app_base_url.rstrip('/')}/scans/{scan_id}"


def _severity_label(notification: Notification) -> str:
    severity = normalize_severity(notification.severity) or "info"
    return _SEVERITY_LABEL.get(severity, severity.upper())


def _email_subject(notification: Notification) -> str:
    return f"[CyberOps] [{_severity_label(notification)}] {notification.title}"


def build_email_message(notification: Notification) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = _email_subject(notification)
    message["From"] = (
        f"{settings.smtp_from_name} <{settings.smtp_from}>"
        if settings.smtp_from_name
        else settings.smtp_from
    )
    message["To"] = notification.destination or ""
    message["Date"] = format_datetime(datetime.now(UTC))

    severity = _severity_label(notification)
    lines = [
        notification.title,
        "",
        notification.body or "",
        "",
        f"Рівень ризику: {severity}",
    ]
    link = _scan_link(notification.scan_id)
    if link:
        lines.append(f"Деталі сканування: {link}")
    lines.append(f"Сповіщення #{notification.id} · CyberOps PRO")
    message.set_content("\n".join(lines).strip() + "\n")

    body_html = html.escape(notification.body or "")
    title_html = html.escape(notification.title)
    scan_html = (
        f'<p><a href="{html.escape(link)}">Деталі сканування</a></p>' if link else ""
    )
    message.add_alternative(
        "<html><body>"
        f"<h3>{title_html}</h3>"
        f"<p>{body_html}</p>"
        f"<p><b>Рівень ризику:</b> {severity}</p>"
        f"{scan_html}"
        f"<hr><small>Сповіщення #{notification.id} · CyberOps PRO</small>"
        "</body></html>",
        subtype="html",
    )
    return message


def _send_smtp_sync(message: EmailMessage) -> None:
    recipients = [message["To"]]
    timeout = settings.smtp_timeout_seconds
    if settings.smtp_ssl:
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=timeout
        )
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
    try:
        client.ehlo()
        if settings.smtp_starttls and not settings.smtp_ssl:
            client.starttls()
            client.ehlo()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message, to_addrs=recipients)
    finally:
        try:
            client.quit()
        except Exception:  # сервер уже закрив з'єднання, це не помилка
            client.close()


async def send_email(notification: Notification) -> None:
    if not settings.smtp_host:
        raise DeliveryError("SMTP_HOST не заданий")
    try:
        await asyncio.to_thread(_send_smtp_sync, build_email_message(notification))
    except DeliveryError:
        raise
    except Exception as exc:
        raise DeliveryError(f"SMTP: {exc}") from exc


def build_telegram_text(notification: Notification) -> str:
    severity = _severity_label(notification)
    parts = [
        f"<b>{html.escape(notification.title)}</b>",
        "",
        html.escape(notification.body or ""),
        "",
        f"<b>Рівень ризику:</b> {severity}",
    ]
    link = _scan_link(notification.scan_id)
    if link:
        parts.append(f'<a href="{html.escape(link)}">Деталі сканування</a>')
    text = "\n".join(parts).strip()
    limit = settings.telegram_max_message_length - _TELEGRAM_RESERVE
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


async def send_telegram(notification: Notification) -> None:
    chat_id = notification.destination
    if not chat_id:
        raise DeliveryError("telegram chat id не заданий")
    if not settings.telegram_bot_token:
        raise DeliveryError("TELEGRAM_BOT_TOKEN не заданий")
    url = f"{settings.telegram_api_base.rstrip('/')}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": build_telegram_text(notification),
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.telegram_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        raise DeliveryError(f"Telegram: {exc}") from exc


async def deliver(notification: Notification) -> DeliveryResult:
    """Доставляє зовнішнім каналом. Не кидає — повертає підсумковий статус."""
    channel = notification.channel
    if channel not in (CHANNEL_EMAIL, CHANNEL_TELEGRAM):
        return DeliveryResult(STATUS_SKIPPED, f"канал {channel} не є зовнішнім")
    if not notification.destination:
        return DeliveryResult(STATUS_SKIPPED, "немає адреси призначення")
    if not channel_available(channel):
        return DeliveryResult(STATUS_SKIPPED, f"канал {channel} вимкнено на сервері")
    try:
        if channel == CHANNEL_EMAIL:
            await send_email(notification)
        else:
            await send_telegram(notification)
    except DeliveryError as exc:
        logger.warning(
            "notification_delivery_failed",
            extra={"channel": channel, "notification_id": notification.id, "error": str(exc)},
        )
        return DeliveryResult(STATUS_FAILED, str(exc)[:500])
    return DeliveryResult(STATUS_SENT)
