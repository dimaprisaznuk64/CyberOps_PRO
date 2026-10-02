"""Релей WebSocket у gateway: `/ws` наскріз.

`gateway/main.py` проксіює `/ws` на `core` через справжній `websockets.connect`
— єдине місце в проєкті, де gateway говорить не по HTTP. Жодного тесту на нього
не було: `test_realtime.py` перевіряє `/ws` у `core` напряму, минаючи gateway,
а `test_gateway.py` — тільки HTTP-маршрути. Тобто весь релей жив у проді без
перевірки, і саме в ньому був баг (див. тест нижче про від'єднання).

Тести справжні: піднімається uvicorn, клієнт під'єднується справжнім
`websockets`. Причина — версії. `websockets` стояв у `gateway/requirements.txt`
як `==12.*`, тобто образ gateway ставив 12.0, поки тести й локальне оточення
підхоплювали 17.1 транзитивно (через `uvicorn[standard]`). `websockets.connect`
жив у двох середовищах, і жодне не перевіряло друге. Тест, який піднімає
справжній релей, робить версію перевіреною, а не припущенням.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import uvicorn
import websockets
from fastapi import FastAPI, WebSocket
from gateway.config import settings as gateway_settings
from gateway.main import app as gateway_app
from starlette.testclient import TestClient

from app.services.auth import create_token
from app.services.realtime import publish_event

# Скільки чекати на старт сервера: у CI під навантаженням uvicorn піднімається
# не миттєво, тож тест не повинен падати через повільний CI.
SERVER_START_ATTEMPTS = 500
SERVER_STOP_TIMEOUT = 10.0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _serve(app: FastAPI, port: int) -> tuple[uvicorn.Server, asyncio.Task]:
    """Піднімає uvicorn у поточному event loop і чекає готовності.

    У тому ж loop, а не в окремому потоці: `publish_event` кладе повідомлення
    в `asyncio.Queue` менеджера realtime, а черга не потокобезпечна — `put_nowait`
    з іншого потоку поводився б непередбачувано.
    """
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    for _ in range(SERVER_START_ATTEMPTS):
        if server.started:
            return server, task
        await asyncio.sleep(0.01)
    task.cancel()
    raise AssertionError(f"uvicorn не піднявся на порту {port}")


async def _stop(server: uvicorn.Server, task: asyncio.Task) -> None:
    server.should_exit = True
    await asyncio.wait_for(task, timeout=SERVER_STOP_TIMEOUT)


class EchoUpstream:
    """Мінімальний upstream: віддзеркалює кожне повідомлення назад.

    Окремий від `core`, щоб відрізнити «релей не працює» від «upstream нічого не
    надіслав». `core` надсилає події лише за `publish_event`, а ехо-сервер
    відповідає на те, що йому надіслали, тож обидва напрямки видно без залежності
    від БД і realtime-режиму.

    `closed` рахує обриви з боку upstream: саме воно показало баг із витоку —
    релей не закривав це з'єднання після від'єднання браузера.
    """

    def __init__(self) -> None:
        self.opened = 0
        self.closed = 0
        self.app = FastAPI()

        @self.app.websocket("/ws")
        async def _echo(websocket: WebSocket) -> None:
            self.opened += 1
            await websocket.accept()
            try:
                while True:
                    message = await websocket.receive_text()
                    await websocket.send_text(f"echo:{message}")
            except Exception:
                self.closed += 1
                return


@pytest_asyncio.fixture
async def echo_upstream(monkeypatch) -> AsyncIterator[EchoUpstream]:
    upstream = EchoUpstream()
    port = _free_port()
    server, task = await _serve(upstream.app, port)
    monkeypatch.setattr(gateway_settings, "core_service_url", f"http://127.0.0.1:{port}")
    try:
        yield upstream
    finally:
        await _stop(server, task)


@pytest_asyncio.fixture
async def gateway_url(echo_upstream: EchoUpstream) -> AsyncIterator[str]:
    """Живий gateway, у якому `core_service_url` уже переставлено на ехо-upstream."""
    port = _free_port()
    server, task = await _serve(gateway_app, port)
    try:
        yield f"ws://127.0.0.1:{port}"
    finally:
        await _stop(server, task)


@pytest_asyncio.fixture
async def end_to_end_url() -> AsyncIterator[str]:
    """Справжні `core` і gateway: подія проходить весь шлях до браузера."""
    from app.main import app as core_app

    core_port = _free_port()
    core_server, core_task = await _serve(core_app, core_port)
    previous = gateway_settings.core_service_url
    gateway_settings.core_service_url = f"http://127.0.0.1:{core_port}"
    gateway_port = _free_port()
    gateway_server, gateway_task = await _serve(gateway_app, gateway_port)
    try:
        yield f"ws://127.0.0.1:{gateway_port}"
    finally:
        gateway_settings.core_service_url = previous
        await _stop(gateway_server, gateway_task)
        await _stop(core_server, core_task)


def test_gateway_rejects_ws_without_valid_token() -> None:
    """Без валідного токена релей не відкривається — і не йде в upstream.

    Через `TestClient`, а не живий сервер: `ws_proxy` закриває з'єднання з кодом
    4401 ще до `websockets.connect`, тож upstream для цього тесту не потрібен, а
    handshake-error від реального сервера залежав би від трактування 403 клієнтом.
    """
    with TestClient(gateway_app) as client:
        with pytest.raises(Exception) as exc:
            with client.websocket_connect("/ws?token=not-a-jwt"):
                pass
    assert getattr(exc.value, "code", None) == 4401


async def test_relay_forwards_browser_message_to_upstream(
    gateway_url: str, echo_upstream: EchoUpstream
) -> None:
    """Браузер -> upstream: gateway передає текст без спотворень."""
    async with websockets.connect(
        f"{gateway_url}/ws?token={create_token(42)}"
    ) as ws:
        await ws.send("hello")
        assert await asyncio.wait_for(ws.recv(), timeout=5) == "echo:hello"
    assert echo_upstream.opened == 1


async def test_relay_forwards_upstream_message_to_browser(gateway_url: str) -> None:
    """Upstream -> браузер: відповідь upstream доходить через gateway.

    Ключова перевірка для версій: отримане повідомлення — це результат
    `websockets.connect` на боці gateway. Якби пін `websockets` у
    `gateway/requirements.txt` був не той, на якому цей тест біжить, API
    `connect` відрізнявся б і тест це побачив би.
    """
    payload = json.dumps({"type": "scan.completed", "scan_id": 7})
    async with websockets.connect(
        f"{gateway_url}/ws?token={create_token(42)}"
    ) as ws:
        await ws.send(payload)
        assert await asyncio.wait_for(ws.recv(), timeout=5) == f"echo:{payload}"


async def test_relay_closes_upstream_when_browser_disconnects(
    gateway_url: str, echo_upstream: EchoUpstream
) -> None:
    """Від'єднання браузера має закривати upstream, а не лишати його відкритим.

    Регресія на `asyncio.gather(browser_to_upstream(), upstream_to_browser())`.
    `gather` чекає обидва напрямки: коли браузер іде, `browser_to_upstream`
    повертається, але `upstream_to_browser` намерло чекає наступного повідомлення
    в `async for`. Жоден не доходив до кінця, `async with` не виходив, тож
    upstream-з'єднання лишалося відкритим — навіки, до рестарту сервісу. Три
    відключення підряд давали `opened: 3, closed: 0`.

    Другий бік тієї самої поломки: uvicorn не завершувався (`docker stop`
    зависав), бо чекав на websocket-обробники, які не завершувалися. Тому
    fixture `_stop` має таймаут — зі зламаним релеєм тест впав би на ньому.
    """
    for _ in range(3):
        async with websockets.connect(
            f"{gateway_url}/ws?token={create_token(42)}"
        ) as ws:
            await ws.send("ping")
            await asyncio.wait_for(ws.recv(), timeout=5)

    assert echo_upstream.opened == 3
    # Кожне з'єднання upstream має бути закрито після від'єднаження браузера.
    # Не миттєво: закриття проходить через ехіку релея, тож даємо трохи часу.
    for _ in range(100):
        if echo_upstream.closed == echo_upstream.opened:
            break
        await asyncio.sleep(0.05)
    assert echo_upstream.closed == echo_upstream.opened, (
        f"upstream-з'єднання лишилися відкритими: "
        f"відкрито {echo_upstream.opened}, закрито {echo_upstream.closed}"
    )


async def test_realtime_event_travels_browser_gateway_core(end_to_end_url: str) -> None:
    """Енд-тенд: подія з `publish_event` доходить до браузера через gateway.

    Саме цей шлях відтворює стенд, але жоден тест і жоден стенд не перевіряли
    його результат: `smoke.sh` дивиться на health і трейси, а `test_realtime.py`
    під'єднується до `core`, минаючи gateway.
    """
    token = create_token(42, "access")
    async with websockets.connect(f"{end_to_end_url}/ws?token={token}") as ws:
        data = None
        for _ in range(20):
            await publish_event(42, "scan.completed", {"scan_id": 7})
            try:
                data = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.5))
            except TimeoutError:
                continue
            break
        assert data is not None, "подія не дійшла до браузера через gateway"

    assert data["type"] == "scan.completed"
    assert data["scan_id"] == 7
