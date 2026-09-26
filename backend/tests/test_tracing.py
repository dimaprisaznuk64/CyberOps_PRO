from __future__ import annotations

import pytest
from app.config import settings
from app.services import tracing
from app.services.tracing import get_tracer, init_tracing, reset_tracing, setup_tracing
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


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
