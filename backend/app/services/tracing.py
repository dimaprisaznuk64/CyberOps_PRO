from __future__ import annotations

from typing import Any

from opentelemetry import trace

# OTel дозволяє зареєструвати провайдера глобально лише один раз, тому
# ініціалізація має бути ідемпотентною: інакше повторний виклик (Celery
# prefork, тести) просто мовчки лишиться без експорту.
_PROVIDER: Any = None

# Скрейп Prometheus бʼє ці шляхи кожні 15с. Без виключення вони дають
# ~5.7 тис. сміттєвих спанів на добу, які засмічують Jaeger. Формат —
# саме такий, який очікує OTel (comma-separated, парситься через split).
_NOISY_URLS = "metrics,health,favicon.ico"


def get_tracer(name: str) -> Any:
    # Беремо трасер із нашого провайдера, а не з глобального: OTel забороняє
    # перевизначати глобальний TracerProvider, тож після першої ініціалізації
    # глобальний може лишитись no-op (і спани пішли б у нікуди).
    if _PROVIDER is not None:
        return _PROVIDER.get_tracer(name)
    return trace.get_tracer(name)


def init_tracing(exporter: Any | None = None) -> Any | None:
    """Піднімає TracerProvider з OTLP-експортером. Повертає None, якщо
    tracing вимкнено або вже ініціалізовано.

    `exporter` існує для тестів: замість реального OTLP можна підкласти
    InMemorySpanExporter і перевірити спани без колектора.
    """
    global _PROVIDER

    from app.config import settings

    if not settings.tracing_enabled:
        return None
    if _PROVIDER is not None:
        return _PROVIDER

    from opentelemetry import trace as otel_trace
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
    otel_trace.set_tracer_provider(provider)
    _PROVIDER = provider
    return provider


def setup_tracing(app: Any) -> Any | None:
    """Інструментує FastAPI-додаток (автотрейс запитів) + OTLP-експорт."""
    provider = init_tracing()
    if provider is None:
        return None

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # Prometheus скрейпить /metrics кожні 15с — без виключення це ~5.7 тис.
    # сміттєвих спанів на добу на сервіс, які нічого не дають у Jaeger.
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls=_NOISY_URLS
    )

    # instrument_app() лише ПІДМІНЯЄ build_middleware_stack, але сам її не
    # викликає, а Starlette будує стек на першому ASGI-виклику — тобто ще
    # до lifespan. Виклик setup_tracing() усередині lifespan (у нас так і
    # було) тому пізніший за стек, і повторно його вже ніхто не збере:
    # middleware не потрапляє в ланцюг, автотрек Requests мовчить, а жодного
    # винятку не видно. Перебудовуємо стек, якщо він уже існує.
    if getattr(app, "middleware_stack", None) is not None:
        app.middleware_stack = app.build_middleware_stack()
    return provider


def reset_tracing() -> None:
    """Скидає глобальний провайдер (лише для тестів)."""
    global _PROVIDER

    _PROVIDER = None
