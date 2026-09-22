from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.dependencies import get_current_user
from app.models.user import ROLE_USER, User
from app.schemas.user import PasswordChange, Token, UserCreate, UserLogin, UserOut
from app.services.auth import (
    authenticate,
    create_token,
    hash_password,
    validate_role,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, session: AsyncSession = Depends(get_session)):
    if not validate_role(payload.role):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Невалідна роль")
    exists = await session.scalar(select(User.id).where(User.username == payload.username))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Користувач вже існує")
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role or ROLE_USER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, session: AsyncSession = Depends(get_session)):
    user = await authenticate(session, payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невірний логін або пароль")
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return Token(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/refresh", response_model=Token)
async def refresh(
    refresh_token: str,
    session: AsyncSession = Depends(get_session),
):
    user_id = decode_refresh(refresh_token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недійсний refresh-токен")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Користувач неактивний")
    return Token(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Поточний пароль невірний")
    user.password_hash = hash_password(payload.new_password)
    await session.commit()


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


def decode_refresh(token: str) -> int | None:
    from app.services.auth import decode_token

    return decode_token(token, expected_type="refresh")
