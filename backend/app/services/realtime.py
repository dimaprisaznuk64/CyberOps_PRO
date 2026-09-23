from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket
from redis import asyncio as aioredis

from app.config import settings

MESSAGE_SCAN_COMPLETED = "scan.completed"
MESSAGE_NOTIFICATION_CREATED = "notification.created"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._queue: asyncio.Queue[tuple[int, dict]] | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._queue = asyncio.Queue()
        self._task = asyncio.create_task(self._consume())

    async def _consume(self) -> None:
        while True:
            user_id, message = await self._queue.get()
            await self.dispatch(user_id, message)

    def enqueue(self, user_id: int, message: dict) -> None:
        if self._queue is not None:
            self._queue.put_nowait((user_id, message))

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        connected = self._connections.get(user_id)
        if connected is None:
            return
        connected.discard(websocket)
        if not connected:
            self._connections.pop(user_id, None)

    async def dispatch(self, user_id: int, message: dict) -> None:
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                await self.disconnect(user_id, websocket)


manager = ConnectionManager()


async def publish_event(
    user_id: int | None, event_type: str, data: dict | None = None
) -> None:
    if user_id is None:
        return
    message = {"type": event_type, **({} if data is None else data)}
    if settings.realtime_mode == "redis":
        try:
            client = aioredis.from_url(settings.celery_broker_url)
            await client.publish(
                settings.realtime_channel,
                json.dumps({"user_id": user_id, "message": message}),
            )
            await client.aclose()
        except Exception:
            return
    else:
        manager.enqueue(user_id, message)


async def run_event_listener() -> None:
    while settings.realtime_mode == "redis":
        try:
            client = aioredis.from_url(settings.celery_broker_url)
            pubsub = client.pubsub()
            await pubsub.subscribe(settings.realtime_channel)
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    payload = json.loads(raw["data"])
                except (TypeError, ValueError):
                    continue
                manager.enqueue(payload["user_id"], payload["message"])
        except Exception:
            await asyncio.sleep(5)