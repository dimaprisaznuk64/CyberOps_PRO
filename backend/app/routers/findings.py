from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user
from app.models.finding import SEVERITIES, Finding
from app.models.scan import Scan
from app.models.user import User
from app.schemas.finding import FindingOut

router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


@router.get("", response_model=list[FindingOut])
async def list_findings(
    severity: str | None = None,
    scan_id: int | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if severity is not None and severity not in SEVERITIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Невалідна серйозність (info|low|medium|high|critical)",
        )
    query = select(Finding).order_by(Finding.id.desc())
    if user.role not in ("admin", "analyst"):
        query = query.join(Scan, Finding.scan_id == Scan.id).where(
            Scan.created_by == user.id
        )
    if severity is not None:
        query = query.where(Finding.severity == severity)
    if scan_id is not None:
        query = query.where(Finding.scan_id == scan_id)
    result = await session.scalars(query)
    return list(result.all())
