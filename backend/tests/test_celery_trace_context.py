"""Слід сканування не має розриватися на черзі Celery.

Симптом живого стенду: у Jaeger `scan.run` приходив як окремий трейс з
одним спаном і одним процесом, тобто кореневим. Причина: `enqueue_scan`
кладе повідомлення в чергу без trace context, а `run_scan` створює спан
без батька. Слід розривався на два — «користувач натиснув скан» у gateway
і «що зробив nmap» у worker, — і в UI між ними було неможливо перейти.
Найдовша операція системи (до `nmap_timeout_seconds`) лишалась без зв'язку
з причиною, яка її викликала.

Жоден стенд цього не помічав: `smoke.sh` скан не запускає, а CI
перевіряє лише імена сервісів у Jaeger, а не їхню спорідненість.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from workers import tasks as worker_tasks

from app import tasks as app_tasks
from app.config import settings
from app.services.tracing import (
    extract_celery_context,
    get_tracer,
    init_tracing,
    inject_celery_headers,
    reset_tracing,
)


@pytest.fixture
def spans(monkeypatch):
    """InMemory-експортер замість OTLP: спани перевіряються без колектора."""
    monkeypatch.setattr(settings, "tracing_enabled", True)
    monkeypatch.setattr(settings, "tracing_service_name", "trace-context-test")
    reset_tracing()
    exporter = InMemorySpanExporter()
    provider = init_tracing(exporter=exporter)
    assert provider is not None

    def _all():
        provider.force_flush()
        return exporter.get_finished_spans()

    def _by_name(name):
        for span in _all():
            if span.name == name:
                return span
        raise AssertionError(f"спан {name!r} не експортувався")

    _by_name.all = _all  # type: ignore[attr-defined]
    yield _by_name
    reset_tracing()


def _context_of(context):
    """Дістає span context із OTel Context, не плутаючи його з самим Context.

    Через `get_current_span()`, а не прямим доступом до ключа: ключі в
    Context namespаяться uuid-ом (`current-span-<uuid>`), тож прямий доступ —
    це прив'язка до внутрішньої реалізації.
    """
    return otel_trace.get_current_span(context).get_span_context()


async def test_span_joins_the_trace_of_whatever_queued_it(spans):
    """Головний інваріант: `scan.run` — дитина спану, що поставив скан."""
    with get_tracer("core").start_as_current_span("POST /api/v1/scans") as request:
        headers = inject_celery_headers()
    request_context = request.get_span_context()

    # Повідомлення йде через Redis і приходить у воркер в іншому процесі —
    # єдине, що лишається спільним, це сам carrier.
    parent = extract_celery_context(headers)
    get_tracer("workers.tasks").start_span("scan.run", context=parent).end()

    scan_span = spans("scan.run")
    assert scan_span.parent is not None, (
        "scan.run лишився коренем — контекст не перенісся через чергу"
    )
    assert scan_span.parent.span_id == request_context.span_id
    assert scan_span.context.trace_id == request_context.trace_id
    # Той самий trace_id — це і є «один слід замість двох».
    assert scan_span.context.span_id != request_context.span_id


async def test_enqueue_scan_actually_sends_the_headers(monkeypatch, spans):
    """Перевірка на живому producer'і: інваріант вище не має чого
    перевіряти, якщо extract приймає порожній carrier — тобто якби
    `enqueue_scan` не кладав headers узагалі."""
    captured: dict = {}

    def _fake_send_task(name, args=None, kwargs=None, headers=None, **_kw):
        captured["name"] = name
        captured["headers"] = headers
        return None

    monkeypatch.setattr(app_tasks.celery_client, "send_task", _fake_send_task)

    with get_tracer("core").start_as_current_span("POST /api/v1/scans") as request:
        app_tasks.enqueue_scan(42, "127.0.0.1", "quick", None)

    assert captured["name"] == app_tasks.SCAN_TASK_NAME
    assert "traceparent" in (captured["headers"] or {}), captured

    parent = extract_celery_context(captured["headers"])
    assert parent is not None
    assert _context_of(parent).span_id == request.get_span_context().span_id


def test_worker_reads_headers_from_the_task_request(monkeypatch, spans):
    """`run_scan` мусить діставати контекст із повідомлення і передавати
    його в `_run_scan`, а не ігнорувати `self.request.headers`.

    Синхронний тест навмисно: `run_scan` викликає `asyncio.run()`, а всередині
    вже запущеного event loop це падає. Воркер синхронний за побудовою, тож
    й тест має бути таким самим.

    `apply(headers=...)`, а не прямий виклик таска: `Task.__call__` сам
    пушить новий request лише з args/kwargs, тож покладений уручну
    `traceparent` він би затёр.
    """
    seen: dict = {}

    def _fake_run_scan(scan_id, host, scan_type, ports, parent=None):
        seen["parent"] = parent
        return {"status": "done"}

    monkeypatch.setattr(worker_tasks, "_run_scan", _fake_run_scan)

    with get_tracer("core").start_as_current_span("POST /api/v1/scans") as request:
        headers = inject_celery_headers()

    worker_tasks.run_scan.apply(args=[1, "127.0.0.1", "quick", None], headers=headers)

    assert seen["parent"] is not None, "run_scan не передав контекст у _run_scan"
    assert _context_of(seen["parent"]).span_id == request.get_span_context().span_id


async def test_scan_without_headers_still_works(spans):
    """Регресія: повідомлення без контексту (старе, що вже лежало в черзі,
    або виклик таска напряму) не має падати — спан просто стає коренем."""
    for headers in (None, {}, {"traceparent": ""}, {"unrelated": "value"}):
        parent = extract_celery_context(headers)
        get_tracer("workers.tasks").start_span("scan.run", context=parent).end()

    found = [s for s in spans.all() if s.name == "scan.run"]
    assert len(found) == 4
    assert all(s.parent is None for s in found)


async def test_worker_scan_span_is_actually_a_child(spans, worker_env):
    """Те саме, але через справжній `_run_scan`: інваріант має триматися на
    реальному місці створення спану, а не лише на сигнатурі."""
    from app.models.scan import SCAN_DONE

    with get_tracer("core").start_as_current_span("POST /api/v1/scans") as request:
        headers = inject_celery_headers()

    result = await worker_tasks._run_scan(
        1, "127.0.0.1", "tcp", None, parent=extract_celery_context(headers)
    )
    assert result["status"] == SCAN_DONE

    scan_span = spans("scan.run")
    assert scan_span.parent is not None
    assert scan_span.parent.span_id == request.get_span_context().span_id
    assert scan_span.attributes["scan.id"] == 1
