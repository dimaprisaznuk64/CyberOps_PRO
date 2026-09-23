from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.user import RoleUpdate, UserOut, UserUpdate
from app.services.auth import validate_role

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.scalars(select(User).order_by(User.id))
    return list(result.all())


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and not validate_role(data["role"]):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Невалідна роль")
    for k, v in data.items():
        setattr(user, k, v)
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=UserOut)
async def change_role(
    user_id: int,
    payload: RoleUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if not validate_role(payload.role):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Невалідна роль")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")
    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Не можна видалити себе")
    await session.delete(user)
    await session.commit()
