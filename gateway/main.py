from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import websockets
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, generate_latest
from starlette.responses import JSONResponse, StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from gateway.config import settings
from gateway.helpers import (
    PUBLIC_PATHS,
    RESPONSE_STRIPPED_HEADERS,
    build_forward_headers,
    resolve_service,
)
from gateway.security import decode_access_token

logger = logging.getLogger("gateway")

gateway_requests_total = Counter(
    "gateway_requests_total",
    "Requests handled by the API Gateway",
    ["service", "method", "status"],
)
gateway_ws_connections_total = Counter(
    "gateway_ws_connections_total",
    "WebSocket connections relayed by the API Gateway",
    ["outcome"],
)

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

MESSAGE_DENIED = JSONResponse({"detail": "Не авторизовано"}, status_code=401)
MESSAGE_NOT_FOUND = JSONResponse({"detail": "Not Found"}, status_code=404)


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def _identity(request: Request) -> dict | None:
    token = _bearer_token(request)
    return decode_access_token(token) if token is not None else None


def _upstreams(app: FastAPI) -> dict[str, httpx.AsyncClient]:
    upstreams = getattr(app.state, "upstreams", None)
    if upstreams is None:
        upstreams = {
            "auth": httpx.AsyncClient(
                base_url=settings.auth_service_url,
                timeout=httpx.Timeout(settings.upstream_timeout_seconds, connect=5.0),
            ),
            "core": httpx.AsyncClient(
                base_url=settings.core_service_url,
                timeout=httpx.Timeout(settings.upstream_timeout_seconds, connect=5.0),
            ),
        }
        app.state.upstreams = upstreams
    return upstreams


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.upstreams = _upstreams(app)
    yield
    upstreams = getattr(app.state, "upstreams", None)
    if upstreams is not None:
        for client in upstreams.values():
            await client.aclose()
        app.state.upstreams = None


app = FastAPI(
    title="CyberOps API Gateway",
    version="0.7.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _forward(request: Request, identity: dict | None) -> Response:
    path = request.url.path
    if path.startswith("/dashboard"):
        service = "core"
    elif path.startswith("/api"):
        service = resolve_service(path)
        if path not in PUBLIC_PATHS and identity is None:
            gateway_requests_total.labels(
                service=service, method=request.method, status="401"
            ).inc()
            return MESSAGE_DENIED
    else:
        return MESSAGE_NOT_FOUND

    body = await request.body()
    headers = build_forward_headers(
        request.headers, identity, request.client.host if request.client else None
    )
    upstream = _upstreams(request.app)[service]
    upstream_request = upstream.build_request(
        request.method,
        path,
        params=request.url.query or None,
        headers=headers,
        content=body or None,
    )
    upstream_response = await upstream.send(upstream_request, stream=True)
    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in RESPONSE_STRIPPED_HEADERS
    }

    async def _stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream_response.aiter_bytes():
                yield chunk
        finally:
            await upstream_response.aclose()

    gateway_requests_total.labels(
        service=service, method=request.method, status=str(upstream_response.status_code)
    ).inc()
    return StreamingResponse(
        _stream(), status_code=upstream_response.status_code, headers=response_headers
    )


@app.get("/health")
async def health(request: Request):
    results: dict[str, str] = {}
    for name, client in _upstreams(request.app).items():
        try:
            resp = await client.get("/health")
            results[name] = "ok" if resp.status_code == 200 else f"status:{resp.status_code}"
        except Exception:
            results[name] = "down"
    ok = all(value == "ok" for value in results.values())
    gateway_requests_total.labels(
        service="health", method="GET", status="200" if ok else "503"
    ).inc()
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "services": results},
        status_code=200 if ok else 503,
    )


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        headers={"Content-Type": METRICS_CONTENT_TYPE},
    )


@app.websocket("/ws")
async def ws_proxy(websocket: WebSocket, token: str = ""):
    if decode_access_token(token) is None:
        gateway_ws_connections_total.labels(outcome="rejected").inc()
        await websocket.close(code=4401)
        return
    await websocket.accept()
    gateway_ws_connections_total.labels(outcome="accepted").inc()

    core_url = settings.core_service_url.replace("http://", "ws://").replace(
        "https://", "wss://"
    )
    target = f"{core_url}/ws?token={token}"
    try:
        async with websockets.connect(target, open_timeout=10) as upstream:

            async def browser_to_upstream():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def upstream_to_browser():
                try:
                    async for data in upstream:
                        if isinstance(data, bytes):
                            await websocket.send_bytes(data)
                        else:
                            await websocket.send_text(data)
                except WebSocketDisconnect:
                    return

            await asyncio.gather(browser_to_upstream(), upstream_to_browser())
    except (WebSocketDisconnect, websockets.exceptions.ConnectionClosed):
        return
    except Exception as exc:
        logger.warning("ws_relay_failed", extra={"error": str(exc)})
        await websocket.close(code=1011)


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(request: Request) -> Response:
    return await _forward(request, _identity(request))