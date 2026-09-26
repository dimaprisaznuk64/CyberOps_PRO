from __future__ import annotations

AUTH_PREFIXES = ("/api/v1/auth", "/api/v1/users", "/api/v1/audit-logs")

PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
}

# Анонімні ендпоінти, які небезпечно лишати без жорсткого ліміту:
# перебір паролів і mass registration.
AUTH_RATE_LIMITED_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/change-password",
    }
)

STRIPPED_HEADERS = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "te",
        "transfer-encoding",
        "upgrade",
        "x-user-id",
        "x-user-role",
        "x-user-username",
    }
)

RESPONSE_STRIPPED_HEADERS = frozenset({"connection", "keep-alive", "transfer-encoding", "upgrade"})


def resolve_service(path: str) -> str:
    return "auth" if path.startswith(AUTH_PREFIXES) else "core"


def describe_path(path: str) -> str:
    """Обрізає шлях до перших трьох сегментів, щоб метрики не роздувалися
    через path-параметри (напр. /api/v1/notifications/12345)."""
    parts = [part for part in path.strip("/").split("/") if part]
    return "/" + "/".join(parts[:3])


def build_forward_headers(
    request_headers, identity: dict | None, client_host: str | None
) -> dict[str, str]:
    headers = {
        key: value
        for key, value in request_headers.items()
        if key.lower() not in STRIPPED_HEADERS
    }
    if identity is not None:
        if identity.get("sub") is not None:
            headers["X-User-Id"] = str(identity["sub"])
        if identity.get("role"):
            headers["X-User-Role"] = str(identity["role"])
        if identity.get("username"):
            headers["X-User-Username"] = str(identity["username"])
    if client_host:
        headers["X-Forwarded-For"] = client_host
    return headers