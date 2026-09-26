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
from gateway.headers import security_headers
from gateway.helpers import (
    AUTH_RATE_LIMITED_PATHS,
    PUBLIC_PATHS,
    RESPONSE_STRIPPED_HEADERS,
    build_forward_headers,
    describe_path,
    resolve_service,
)
from gateway.ratelimit import BUCKET_API, BUCKET_AUTH, Decision, TokenBucketLimiter
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
gateway_rate_limited_total = Counter(
    "gateway_rate_limited_total",
    "Requests rejected by the rate limiter",
    ["bucket", "path"],
)

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

MESSAGE_DENIED = JSONResponse({"detail": "Не авторизовано"}, status_code=401)
MESSAGE_NOT_FOUND = JSONResponse({"detail": "Not Found"}, status_code=404)

# Методи, які не витрачають квоту: preflight та перевірка живості
_UNLIMITED_METHODS = frozenset({"OPTIONS", "HEAD"})


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def _identity(request: Request) -> dict | None:
    token = _bearer_token(request)
    return decode_access_token(token) if token is not None else None


def _limiters(request: Request) -> dict[str, TokenBucketLimiter]:
    limiters = getattr(request.app.state, "limiters", None)
    if limiters is None:
        limiters = {
            BUCKET_AUTH: TokenBucketLimiter(
                settings.auth_rate_limit_per_minute,
                burst=settings.auth_rate_limit_burst,
                max_keys=settings.rate_limit_max_keys,
            ),
            BUCKET_API: TokenBucketLimiter(
                settings.api_rate_limit_per_minute,
                burst=settings.api_rate_limit_burst,
                max_keys=settings.rate_limit_max_keys,
            ),
        }
        request.app.state.limiters = limiters
    return limiters


def _rate_limit_key(request: Request, identity: dict | None, bucket: str) -> str:
    # Авторизовані запити рахуємо за користувачем: інакше всі юзери за одним NAT
    # (корпоративний вихід, CI) ділять один ліміт. Анонімні — тільки за IP.
    if bucket == BUCKET_API and identity is not None and identity.get("sub") is not None:
        return f"user:{identity['sub']}"
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


def _check_rate_limit(
    request: Request, identity: dict | None, bucket: str
) -> Decision | None:
    if not settings.rate_limit_enabled or request.method in _UNLIMITED_METHODS:
        return None
    key = _rate_limit_key(request, identity, bucket)
    return _limiters(request)[bucket].check(key)


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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    if settings.security_headers_enabled:
        for key, value in security_headers(request.url.path).items():
            response.headers.setdefault(key, value)
    return response


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

    if path.startswith("/api"):
        bucket = BUCKET_AUTH if path in AUTH_RATE_LIMITED_PATHS else BUCKET_API
        decision = _check_rate_limit(request, identity, bucket)
        if decision is not None and not decision.allowed:
            gateway_rate_limited_total.labels(
                bucket=bucket, path=describe_path(path)
            ).inc()
            gateway_requests_total.labels(
                service=service, method=request.method, status="429"
            ).inc()
            logger.warning(
                "rate_limited",
                extra={"bucket": bucket, "path": path, "method": request.method},
            )
            return JSONResponse(
                {"detail": "Забагато запитів. Спробуйте пізніше."},
                status_code=429,
                headers={
                    "Retry-After": str(decision.retry_after),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

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