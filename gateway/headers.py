from __future__ import annotations

from gateway.config import settings

# API віддає JSON, тож дозволяти нічого не потрібно — це максимально суворо.
# frame-ancestors/base-uri/form-action закривають clickjacking і підробку форм.
CSP_STRICT = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# Legacy-дашборд (/dashboard -> mount на legacy/dashboard/) — це
# статична сторінка з інлайновими <style>/<script>, тож їй потрібен unsafe-inline.
# Основний UI (Next.js) йде з окремого контейнера і gateway не проходить.
CSP_STATIC = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
)

_STATIC_PREFIXES = ("/dashboard", "/static", "/assets")


def _is_static(path: str) -> bool:
    return path.startswith(_STATIC_PREFIXES)


def security_headers(path: str) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": CSP_STATIC if _is_static(path) else CSP_STRICT,
        "Cross-Origin-Opener-Policy": "same-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    }
    if settings.hsts_enabled:
        headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age}; includeSubDomains"
        )
    return headers
