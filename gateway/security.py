from __future__ import annotations

from typing import Any

from jose import JWTError, jwt

from gateway.config import settings


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != "access" or payload.get("sub") is None:
        return None
    return payload