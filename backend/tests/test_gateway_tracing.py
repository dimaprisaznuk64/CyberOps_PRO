from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from gateway.config import settings as gateway_settings
from gateway.tracing import get_tracer as gw_get_tracer
from gateway.tracing import init_tracing, reset_tracing, setup_tracing
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind


@pytest.fixture
def gw_exporter(monkeypatch):
    """InMemory-експортер замість OTLP: спани перевіряються без колектора."""
    monkeypatch.setattr(gateway_settings, "tracing_enabled", True)
    monkeypatch.setattr(gateway_settings, "tracing_service_name", "gateway-test")
    reset_tracing()
    exporter = InMemorySpanExporter()
    yield exporter
    reset_tracing()


@contextmanager
def _echo_upstream():
    """Справжній loopback-сервер: httpx-інструментація вшивається в
    AsyncHTTPTransport, тому MockTransport її оминає і нічого не трейсить."""
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(dict(self.headers))
            body = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# ПЕРШИЙ тест у модулі — і це не випадковість. httpx-інструментація
# процесно-глобальна й лишається на весь процес (як у production, де
# setup_tracing викликається один раз). Переставляти його нижче не можна:
# наступний setup_tracing вже не переінструментує httpx, і клієнтські спани
# підуть у провайдер першого тесту.
async def test_upstream_call_gets_client_span_and_trace_context(gw_exporter):
    """Головна цінність інструментації: клієнтський спан на виклик до
    core/auth + проброс traceparent, тобто gateway і core — одна траса."""
    with _echo_upstream() as (base_url, received):
        app = FastAPI()

        @app.get("/api/v1/assets")
        async def proxy():
            async with AsyncClient(base_url=base_url, timeout=5) as upstream:
                resp = await upstream.get("/api/v1/assets")
            return {"upstream_status": resp.status_code}

        provider = init_tracing(exporter=gw_exporter)
        assert setup_tracing(app) is not None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/v1/assets")
        assert resp.status_code == 200
        assert resp.json() == {"upstream_status": 200}

        provider.force_flush()
        spans = gw_exporter.get_finished_spans()
        client_span = next(s for s in spans if s.name == "GET" and s.kind == SpanKind.CLIENT)
        server_span = next(
            s for s in spans if "/api/v1/assets" in s.name and s.kind == SpanKind.SERVER
        )

        assert client_span.parent is not None
        assert client_span.parent.span_id == server_span.context.span_id
        assert client_span.context.trace_id == server_span.context.trace_id

        # upstream мав отримати traceparent саме цього trace
        traceparent = received[0]["traceparent"]
        assert format(client_span.context.trace_id, "032x") in traceparent
        assert format(client_span.context.span_id, "016x") in traceparent


async def test_gateway_tracing_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(gateway_settings, "tracing_enabled", False)
    reset_tracing()
    assert init_tracing() is None
    reset_tracing()


async def test_gateway_provider_carries_service_resource(gw_exporter):
    provider = init_tracing(exporter=gw_exporter)
    assert provider is not None
    assert provider.resource.attributes["service.name"] == "gateway-test"
    assert provider.resource.attributes["service.version"] == gateway_settings.app_version
    assert provider.resource.attributes["deployment.environment"] == gateway_settings.app_env


async def test_gateway_init_is_idempotent(gw_exporter):
    first = init_tracing(exporter=gw_exporter)
    second = init_tracing()
    assert first is second


async def test_gateway_server_span_parents_nested_call(gw_exporter):
    """Будь-яка робота всередині обробки запиту має бути вкладена в
    server-спан gateway, інакше вони пішли б в Jaeger окремими трасами."""
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping():
        with gw_get_tracer("gateway.main").start_as_current_span("upstream.call"):
            pass
        return {"pong": True}

    provider = init_tracing(exporter=gw_exporter)
    assert setup_tracing(app) is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/ping")
    assert resp.status_code == 200

    provider.force_flush()
    spans = gw_exporter.get_finished_spans()
    upstream = next(s for s in spans if s.name == "upstream.call")
    assert upstream.parent is not None

    server = next(
        s for s in spans if s.context.span_id == upstream.parent.span_id
    )
    assert server is not None
    assert server.context.trace_id == upstream.context.trace_id
    assert "/api/v1/ping" in server.name


async def test_gateway_tracer_survives_missing_global_provider(gw_exporter):
    """OTel забороняє перевизначати глобальний TracerProvider, тож після
    першої ініціалізації глобальний може лишитись no-op — треба брати
    трасер із нашого провайдера."""
    provider = init_tracing(exporter=gw_exporter)
    with gw_get_tracer("gateway.main").start_as_current_span("manual"):
        pass
    provider.force_flush()
    assert any(s.name == "manual" for s in gw_exporter.get_finished_spans())


async def test_gateway_setup_without_tracing_is_harmless(monkeypatch):
    monkeypatch.setattr(gateway_settings, "tracing_enabled", False)
    app = FastAPI()
    assert setup_tracing(app) is None
    assert not getattr(app, "_is_instrumented_by_opentelemetry", False)
    reset_tracing()
