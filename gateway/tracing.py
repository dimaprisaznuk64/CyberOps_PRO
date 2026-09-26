from __future__ import annotations

from typing import Any

from opentelemetry import trace

# Це навмисний дубль app/services/tracing.py: gateway живе в окремому образі
# (власний requirements.txt і Dockerfile копіює лише gateway/), тож імпортувати
# backend-модуль він не може. Коли зʼявиться спільний пакет — варто злити.
# Відмінність від backend-варіанта: інструментуємо ще й httpx, бо весь сенс
# інструментації gateway — у клієнтських спанах на виклики до core/auth.
_PROVIDER: Any = None

# Скрейп Prometheus бʼє ці шляхи кожні 15с на кожен сервіс. Без виключення
# це ~5.7 тис. сміттєвих спанів на добу, які засмічують Jaeger.
_NOISY_URLS = "metrics,health,favicon.ico"


def get_tracer(name: str) -> Any:
    if _PROVIDER is not None:
        return _PROVIDER.get_tracer(name)
    return trace.get_tracer(name)


def init_tracing(exporter: Any | None = None) -> Any | None:
    """Піднімає TracerProvider з OTLP-експортером. None, якщо tracing вимкнено
    або вже ініціалізовано. `exporter` — для тестів (InMemorySpanExporter)."""
    global _PROVIDER

    from gateway.config import settings

    if not settings.tracing_enabled:
        return None
    if _PROVIDER is not None:
        return _PROVIDER

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    if exporter is None:
        exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.tracing_service_name,
                "service.version": settings.app_version,
                "deployment.environment": settings.app_env,
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _PROVIDER = provider
    return provider


def setup_tracing(app: Any) -> Any | None:
    """Інструментує FastAPI (server-спани) та httpx (клієнтські спани на
    виклики до core/auth) + OTLP-експорт.

    httpx-інструментація глобальна й моніториться на всі виклики, тож вона
    робить hop gateway→core видимим окремим спаном — саме те, чого бракувало
    для «невидимого» першого хопу.
    """
    provider = init_tracing()
    if provider is None:
        return None

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls=_NOISY_URLS
    )
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    return provider


def reset_tracing() -> None:
    """Скидає глобальний провайдер (лише для тестів)."""
    global _PROVIDER

    _PROVIDER = None
