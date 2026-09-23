from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from app.models.audit_log import AuditLog
from app.services.auth import decode_token
from app.services.metrics import describe_path, http_requests_total

SKIP_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/metrics")
USER_AGENT_MAX = 255


def _bearer_user_id(request: Request) -> int | None:
    auth = request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return decode_token(auth.split(" ", 1)[1].strip(), expected_type="access")


async def audit_middleware(request: Request, call_next) -> Response:
    response = await call_next(request)
    path = request.url.path
    http_requests_total.labels(
        method=request.method,
        path=describe_path(path),
        status=str(response.status_code),
    ).inc()
    if not path.startswith("/api") or path.startswith(SKIP_PREFIXES):
        return response
    factory = getattr(request.app.state, "audit_session_factory", None)
    if factory is None:
        return response
    user_agent = (request.headers.get("user-agent") or "")[:USER_AGENT_MAX] or None
    entry = AuditLog(
        user_id=_bearer_user_id(request),
        method=request.method,
        path=path,
        status_code=response.status_code,
        client_ip=request.client.host if request.client else None,
        user_agent=user_agent,
    )
    async with factory() as session:
        session.add(entry)
        await session.commit()
    return response