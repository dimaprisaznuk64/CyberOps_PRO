from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, require_analyst
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetOut, AssetUpdate
from app.services.asset_risk import EMPTY_RISK, AssetRisk, risk_by_asset
from app.services.netguard import HostNotAllowedError, assert_host_allowed

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


def _visible_query(user: User):
    query = select(Asset).order_by(Asset.id)
    if user.role != "admin":
        query = query.where(Asset.owner_id == user.id)
    return query


def _with_risk(asset: Asset, risk: dict[int, AssetRisk]) -> AssetOut:
    return AssetOut.model_validate(asset).model_copy(update=risk.get(asset.id, EMPTY_RISK))


async def _out(session: AsyncSession, asset: Asset) -> AssetOut:
    """Актив + агрегований ризик (див. app/services/asset_risk.py)."""
    return _with_risk(asset, await risk_by_asset(session, [asset.id]))


def _host_check(kind: str, host: str) -> None:
    if kind == "docker":
        return
    try:
        assert_host_allowed(host)
    except HostNotAllowedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


async def _get_owned_asset(
    session: AsyncSession, asset_id: int, user: User
) -> Asset:
    asset = await session.get(Asset, asset_id)
    if asset is None or (asset.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Актив не знайдено")
    return asset


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _host_check(payload.kind, payload.host)
    asset = Asset(
        name=payload.name,
        host=payload.host,
        kind=payload.kind,
        docker_container=payload.docker_container,
        description=payload.description,
        owner_id=user.id,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return await _out(session, asset)


@router.get("", response_model=list[AssetOut])
async def list_assets(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    assets = list((await session.scalars(_visible_query(user))).all())
    risk = await risk_by_asset(session, [asset.id for asset in assets])
    return [_with_risk(asset, risk) for asset in assets]


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _out(session, await _get_owned_asset(session, asset_id, user))


@router.patch("/{asset_id}", response_model=AssetOut)
async def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    asset = await _get_owned_asset(session, asset_id, user)
    data = payload.model_dump(exclude_unset=True)
    if "host" in data or "kind" in data:
        _host_check(data.get("kind", asset.kind), data.get("host", asset.host))
    for key, value in data.items():
        setattr(asset, key, value)
    await session.commit()
    await session.refresh(asset)
    return await _out(session, asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: int,
    user: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
):
    asset = await _get_owned_asset(session, asset_id, user)
    await session.delete(asset)
    await session.commit()