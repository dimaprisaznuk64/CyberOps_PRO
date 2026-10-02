from __future__ import annotations

from celery import Celery
from prometheus_client import start_http_server

from app.config import settings
from app.services.broker import transport_options as broker_transport_options
from app.services.tracing import init_tracing

# Celery не має FastAPI-додатка, але спани у tasks.py створюються вручну —
# без ініціалізації провайдера вони пішли б у no-op tracer і зникли.
init_tracing()

celery_app = Celery("cyberops_worker", broker=settings.celery_broker_url)
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_transport_options = broker_transport_options()
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.worker_concurrency = 1

# Прибирання завислих сканів: без нього рядок, який воркер не дописав
# (падіння, OOM-рестарт), назавжди світився «в обробці».
celery_app.conf.beat_schedule = {
    "reap-stale-scans": {
        "task": "workers.tasks.reap_stale_scans",
        "schedule": float(settings.scan_reaper_interval_seconds),
    }
}


def serve_metrics() -> None:
    start_http_server(settings.worker_metrics_port)


celery_app.autodiscover_tasks(["workers"], force=True)
