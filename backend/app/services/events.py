from __future__ import annotations

import json
from typing import Any, Protocol

from app.config import settings


class EventPublisher(Protocol):
    def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...


class CollectingPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


class RabbitMQEventPublisher:
    def __init__(self, url: str, exchange: str, enabled: bool = True) -> None:
        self._url = url
        self._exchange = exchange
        self._enabled = enabled

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self._enabled:
            return
        try:
            import pika
        except ImportError:
            return
        try:
            params = pika.URLParameters(self._url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.exchange_declare(
                exchange=self._exchange, exchange_type="topic", durable=True
            )
            channel.basic_publish(
                exchange=self._exchange,
                routing_key=event_type,
                body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json", delivery_mode=2
                ),
            )
            connection.close()
        except Exception:
            return


_publisher: EventPublisher | None = None


def get_publisher() -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = RabbitMQEventPublisher(
            settings.rabbitmq_url, settings.events_exchange, settings.events_enabled
        )
    return _publisher


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    get_publisher().publish(event_type, payload)