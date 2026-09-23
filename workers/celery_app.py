from __future__ import annotations

from app.config import settings
from celery import Celery
from prometheus_client import start_http_server

celery_app = Celery("cyberops_worker", broker=settings.celery_broker_url)
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.worker_concurrency = 1


def serve_metrics() -> None:
    start_http_server(settings.worker_metrics_port)


celery_app.autodiscover_tasks(["workers"], force=True)
