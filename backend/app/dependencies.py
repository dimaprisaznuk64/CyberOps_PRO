from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import ROLE_ADMIN, ROLE_ANALYST, User
from app.services.auth import decode_token, get_user_by_id

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизовано")
    user_id = decode_token(creds.credentials, expected_type="access")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недійсний або прострочений токен")
    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Користувач неактивний або не знайдений")
    return user


def require_role(*roles: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Недостатньо прав")
        return user

    return checker


require_admin = require_role(ROLE_ADMIN)
require_analyst = require_role(ROLE_ANALYST, ROLE_ADMIN)
