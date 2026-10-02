"""Воркер має бачити, що брокер живий — інакше скан висить у pending назавжди.

Симптом (kind-E2E, 2026-10-02): `POST /api/v1/scans` -> 202, далі 60 спроб
три секунди потому статус `pending`. У лозі воркера — нуль рядків про
завдання: жодного `Task workers.tasks.run_scan[...] received`, навіть
`reap_stale_scans`, який celery beat надсивав о 11:27, 11:28 і 11:29.
Тобто повідомлення було в черзі, а консьюмер її не читав.

Причина — не в застосунку, а в транспорті: redis-транспорт celery бере
завдання блокуючим BRPOP, і на напівмертвому з'єднанні цей виклик не
повертається й не падає. Воркер лишається `ready`, скан — `pending`, а
жоден рядок логу не пояснює чому. `health_check_interval` перетворює
таке зависання на таймаут і перепідключення; liveness-probe в манифесті
підстраховує куб, коли зависання все ж станеться.

Ці тести падають, якщо опцію знову знімуть або якщо producer і consumer
розійдуться у налаштуваннях: тоді симптом повертається, а стенд знову
збереться зеленою сліпою.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from celery import Celery

from app.config import Settings, settings
from app.services.broker import transport_options

yaml = pytest.importorskip("yaml", reason="PyYAML приходить з uvicorn[standard]")

ROOT = Path(__file__).resolve().parents[2]
WORKER_MANIFEST = ROOT / "infrastructure" / "kubernetes" / "base" / "worker.yaml"


def _worker_app() -> Celery:
    """Справжній додаток воркера: імпортуємо, бо конфіг це мутація,
    а не аргумент конструктора, і підмінити його ззовні не можна."""
    from workers.celery_app import celery_app

    return celery_app


def _client_app() -> Celery:
    from app.tasks import celery_client

    return celery_client


def test_worker_detects_a_dead_broker_connection():
    """Головний інваріант: без інтервалу перевірки консьюмер BRPOP висить
    намертво, і жоден тест цього не бачить — воркер просто мовчить."""
    options = _worker_app().conf.broker_transport_options

    assert isinstance(options, dict), options
    interval = options.get("health_check_interval")
    assert isinstance(interval, int | float) and interval > 0, (
        f"health_check_interval не задано або він не додатний: {options!r} — "
        "воркер знову здатний зависнути на споживанні мовчки"
    )
    assert options.get("socket_keepalive") is True, (
        f"socket_keepalive вимкнено: {options!r} — 'напівмертве' з'єднання "
        "з redis не помічатиметься"
    )


def test_producer_and_consumer_talk_to_the_broker_identically():
    """Producer (core) і consumer (worker) — різні процеси з різними
    об'єктами Celery. Різні налаштування означали б, що вони говорять з
    брокером не зовсім однаково, а симптом цього — скан назавжди в pending
    без жодного рядка в логах."""
    client, worker = _client_app(), _worker_app()

    assert client.conf.broker_url == worker.conf.broker_url
    assert client.conf.broker_transport_options == worker.conf.broker_transport_options
    assert client.conf.broker_transport_options == transport_options()


def test_interval_is_configurable_and_sane():
    """Значення має бути налаштовуваним (стенд може бути іншим), але
    не нульовим: нуль вимикає рівно те, заради чого це введено."""
    assert settings.celery_broker_health_check_interval > 0

    fast = Settings(celery_broker_health_check_interval=5)
    assert fast.celery_broker_health_check_interval == 5


def test_k8s_restarts_a_worker_that_stopped_consuming():
    """Манифест — друга половина захисту. Без liveness куб не відрізняє
    «працює» від «завис»: pod лишається Running, і підвіс тримає систему
    у стані, який виглядає живим."""
    docs = [d for d in yaml.safe_load_all(WORKER_MANIFEST.read_text(encoding="utf-8"))
            if d and d.get("kind") == "Deployment"]
    assert len(docs) == 1, "очікувався рівно один Deployment worker"
    container = docs[0]["spec"]["template"]["spec"]["containers"][0]
    probe = container.get("livenessProbe")
    assert probe, "у worker немає livenessProbe — завислий воркер не перезапуститься"

    command = " ".join(probe["exec"]["command"])
    assert "inspect ping" in command, command
    # `inspect ping` без `-d` виходить з кодом 0, навіть якщо не відповів
    # ніхто: порожній вивід. Тобто така перевірка завжди була б зеленою.
    assert "-d" in command, (
        f"перевірка не обмежена цим воркером: {command} — вона зелена, поки "
        "хтось відповідає, і мертва навіть якщо worker мовчить"
    )
    assert "grep -q pong" in command, (
        f"перевірка не перевіряє вивід: {command} — 'мовчить' діє кодом 0, "
        "а не помилкою, тож рестарту не буде"
    )
    assert probe.get("failureThreshold", 3) >= 2, (
        "failureThreshold=1 перезапускає воркер на одному невдалому пінгу"
    )