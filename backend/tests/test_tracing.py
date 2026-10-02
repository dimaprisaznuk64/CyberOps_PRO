from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.config import settings
from app.services import tracing
from app.services.tracing import get_tracer, init_tracing, reset_tracing, setup_tracing


@pytest.fixture
def memory_exporter(monkeypatch):
    """InMemory-експортер замість OTLP: спани перевіряються без колектора."""
    monkeypatch.setattr(settings, "tracing_enabled", True)
    monkeypatch.setattr(settings, "tracing_service_name", "core-test")
    reset_tracing()
    exporter = InMemorySpanExporter()
    yield exporter
    reset_tracing()


async def test_disabled_tracing_is_a_noop(monkeypatch):
    monkeypatch.setattr(settings, "tracing_enabled", False)
    reset_tracing()
    assert init_tracing() is None
    reset_tracing()


async def test_provider_carries_service_resource(memory_exporter):
    provider = init_tracing(exporter=memory_exporter)
    assert provider is not None
    resource = provider.resource
    assert resource.attributes["service.name"] == "core-test"
    assert resource.attributes["deployment.environment"] == settings.app_env
    assert resource.attributes["service.version"] == settings.app_version


async def test_init_is_idempotent(memory_exporter):
    first = init_tracing(exporter=memory_exporter)
    second = init_tracing()
    assert first is second


async def test_fastapi_requests_are_traced(memory_exporter):
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    # спершу піднімаємо провайдера з in-memory експортером, далі інструментуємо
    # додаток (setup_tracing перевикористає вже створений провайдер)
    provider = init_tracing(exporter=memory_exporter)
    assert provider is not None
    assert setup_tracing(app) is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/ping")
    assert resp.status_code == 200

    # флюшити треба провайдера: BatchSpanProcessor тримає спани у своїй черзі
    provider.force_flush()
    spans = memory_exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert any("ping" in name for name in names), names

    traced = next(s for s in spans if "ping" in s.name)
    assert traced.resource.attributes["service.name"] == "core-test"


async def test_manual_span_from_worker_tracer(memory_exporter):
    provider = init_tracing(exporter=memory_exporter)
    tracer = get_tracer("workers.tasks")
    with tracer.start_as_current_span("scan.run", attributes={"scan.id": 7}):
        pass

    provider.force_flush()
    spans = memory_exporter.get_finished_spans()
    scan_span = next(s for s in spans if s.name == "scan.run")
    assert scan_span.attributes["scan.id"] == 7


async def test_setup_tracing_without_instrumentation_is_harmless(monkeypatch, memory_exporter):
    monkeypatch.setattr(settings, "tracing_enabled", False)
    app = FastAPI()
    assert setup_tracing(app) is None
    #FastAPIInstrumentor не мав підчепити додаток
    assert not getattr(app, "_is_instrumented_by_opentelemetry", False)
    tracing.reset_tracing()


async def test_scrape_endpoints_are_not_traced(memory_exporter):
    """Prometheus скрейпить /metrics і /health кожні 15с: ці спани треба
    відкидати, інакше Jaeger засмічується сміттям."""
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    @app.get("/metrics")
    async def metrics():
        return {"traces_total": 1}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    provider = init_tracing(exporter=memory_exporter)
    assert setup_tracing(app) is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for path in ("/ping", "/metrics", "/health", "/metrics"):
            resp = await ac.get(path)
            assert resp.status_code == 200

    provider.force_flush()
    names = [s.name for s in memory_exporter.get_finished_spans()]
    assert any("ping" in name for name in names), names
    assert not any("metrics" in name for name in names), names
    assert not any("health" in name for name in names), names


async def _lifespan_cycle(app, between) -> None:
    """Проводить застосунок через справжній цикл lifespan.

    startup -> between() -> shutdown. Нуково, бо саме тут визначається
    порядок: стек middleware будується на першому ASGI-виклику, а ми
    хочемо перевірити інструментування саме всередині lifespan.
    """
    to_app: asyncio.Queue = asyncio.Queue()
    startup_done = asyncio.Event()

    async def receive():
        return await to_app.get()

    async def send(message):
        if message["type"] == "lifespan.startup.complete":
            startup_done.set()

    task = asyncio.create_task(
        app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send)
    )
    await to_app.put({"type": "lifespan.startup"})
    await asyncio.wait_for(startup_done.wait(), timeout=5)
    await between()
    await to_app.put({"type": "lifespan.shutdown"})
    await asyncio.wait_for(task, timeout=5)


async def test_tracing_still_works_when_setup_runs_in_lifespan(memory_exporter):
    """Регресія: інструментувати додаток усередині lifespan надто пізно.

    Starlette будує стек middleware на першому ASGI-виклику, тобто ДО
    lifespan, а instrument_app() лише підміняє build_middleware_stack, не
    викликаючи її. Старій код мовчки інаструментував застосунок у занадто
    пізній момент: сервіс працював, а з нього не йшов жоден спан — Jaeger
    бачив лише gateway, який інструментує не через FastAPI.
    """
    provider = init_tracing(exporter=memory_exporter)
    assert provider is not None

    @asynccontextmanager
    async def lifespan(app):
        setup_tracing(app)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/ping")
    async def ping():
        return {"pong": True}

    async def call_ping():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/ping")
        assert resp.status_code == 200

    await _lifespan_cycle(app, call_ping)

    provider.force_flush()
    names = [s.name for s in memory_exporter.get_finished_spans()]
    assert any("ping" in name for name in names), names
