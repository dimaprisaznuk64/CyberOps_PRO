from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import ROLES, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(
    user_id: int,
    token_type: str = "access",
    *,
    role: str | None = None,
    username: str | None = None,
) -> str:
    if token_type == "access":
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {"sub": str(user_id), "type": token_type, "exp": expire}
    if role:
        payload["role"] = role
    if username:
        payload["username"] = username
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    sub = payload.get("sub")
    return int(sub) if sub is not None else None


async def authenticate(session: AsyncSession, username: str, password: str) -> User | None:
    result = await session.scalar(select(User).where(User.username == username))
    if result is None or not result.is_active:
        return None
    if not verify_password(password, result.password_hash):
        return None
    return result


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


def validate_role(role: str) -> bool:
    return role in ROLES
