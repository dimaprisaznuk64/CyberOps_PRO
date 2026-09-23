from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, require_analyst
from app.models.target import Target
from app.models.user import User
from app.schemas.target import TargetCreate, TargetOut, TargetUpdate
from app.services.netguard import HostNotAllowedError, assert_host_allowed

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])


def _visible_query(user: User):
    query = select(Target).order_by(Target.id)
    if user.role != "admin":
        query = query.where(Target.owner_id == user.id)
    return query


async def _get_owned_target(
    session: AsyncSession, target_id: int, user: User
) -> Target:
    target = await session.get(Target, target_id)
    if target is None or (target.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ціль не знайдено")
    return target


@router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
async def create_target(
    payload: TargetCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        assert_host_allowed(payload.host)
    except HostNotAllowedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    target = Target(
        name=payload.name,
        host=payload.host,
        description=payload.description,
        owner_id=user.id,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return target


@router.get("", response_model=list[TargetOut])
async def list_targets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.scalars(_visible_query(user))
    return list(result.all())


@router.get("/{target_id}", response_model=TargetOut)
async def get_target(
    target_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_owned_target(session, target_id, user)


@router.patch("/{target_id}", response_model=TargetOut)
async def update_target(
    target_id: int,
    payload: TargetUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    target = await _get_owned_target(session, target_id, user)
    data = payload.model_dump(exclude_unset=True)
    if "host" in data:
        try:
            assert_host_allowed(data["host"])
        except HostNotAllowedError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    for key, value in data.items():
        setattr(target, key, value)
    await session.commit()
    await session.refresh(target)
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: int,
    user: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
):
    target = await _get_owned_target(session, target_id, user)
    await session.delete(target)
    await session.commit()
