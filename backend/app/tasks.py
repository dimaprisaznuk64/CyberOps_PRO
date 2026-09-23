from __future__ import annotations

from celery import Celery

from app.config import settings

celery_client = Celery("cyberops", broker=settings.celery_broker_url)
celery_client.conf.broker_connection_retry_on_startup = True

SCAN_TASK_NAME = "workers.tasks.run_scan"


def enqueue_scan(
    scan_id: int,
    host: str,
    scan_type: str,
    ports: str | None,
) -> None:
    celery_client.send_task(SCAN_TASK_NAME, args=[scan_id, host, scan_type, ports])


def get_task_enqueuer():
    return enqueue_scan
