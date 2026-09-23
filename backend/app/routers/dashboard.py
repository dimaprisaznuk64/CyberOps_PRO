from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.models.asset import Asset
from app.models.notification import Notification
from app.models.scan import Scan
from app.models.user import User
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStats)
async def dashboard_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    privileged = user.role in ("admin", "analyst")
    asset_select = select(Asset) if privileged else select(Asset).where(
        Asset.owner_id == user.id
    )
    scan_select = select(Scan) if privileged else select(Scan).where(
        Scan.created_by == user.id
    )

    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
    )
    total_assets = await session.scalar(
        select(func.count()).select_from(asset_select.subquery())
    )
    scans_sq = scan_select.subquery()
    high_risk = await session.scalar(
        select(func.count())
        .select_from(scans_sq)
        .where(scans_sq.c.risk_level.in_(("HIGH", "CRITICAL")))
    )
    recent = (
        await session.scalars(scan_select.order_by(Scan.id.desc()).limit(10))
    ).all()

    return DashboardStats(
        unread_notifications=unread or 0,
        total_assets=total_assets or 0,
        high_risk_scans=high_risk or 0,
        recent_scans=list(recent),
    )