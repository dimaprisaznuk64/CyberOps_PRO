from __future__ import annotations

from celery import Celery

from app.config import settings

celery_client = Celery("cyberops", broker=settings.celery_broker_url)
celery_client.conf.broker_connection_retry_on_startup = True

SCAN_TASK_NAME = "workers.tasks.run_scan"
NOTIFICATION_DELIVERY_TASK_NAME = "workers.tasks.deliver_notification"


def enqueue_scan(
    scan_id: int,
    host: str,
    scan_type: str,
    ports: str | None,
) -> None:
    celery_client.send_task(SCAN_TASK_NAME, args=[scan_id, host, scan_type, ports])


def enqueue_notification_delivery(notification_id: int) -> None:
    """Доставка зовнішнім каналом винесена в окремий таск, щоб SMTP/Telegram
    не блокували ані API, ані scan-таск."""
    celery_client.send_task(NOTIFICATION_DELIVERY_TASK_NAME, args=[notification_id])


def get_task_enqueuer():
    return enqueue_scan


def get_notification_enqueuer():
    return enqueue_notification_delivery
