from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, require_analyst
from app.models.scan import SCAN_PENDING, Scan
from app.models.target import Target
from app.models.user import User
from app.schemas.scan import ScanCreate, ScanOut, ScanResultOut
from app.services.netguard import HostNotAllowedError, assert_host_allowed
from app.tasks import get_task_enqueuer

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


@router.post("", response_model=ScanOut, status_code=status.HTTP_202_ACCEPTED)
async def create_scan(
    payload: ScanCreate,
    _: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
    enqueue: Callable = Depends(get_task_enqueuer),
):
    if not payload.validate_scan_type():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Невалідний тип сканування (ping|tcp|quick)",
        )
    target = await session.get(Target, payload.target_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ціль не знайдено")
    try:
        assert_host_allowed(target.host)
    except HostNotAllowedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    scan = Scan(
        target_id=target.id,
        created_by=_.id,
        status=SCAN_PENDING,
        scan_type=payload.scan_type,
        ports=payload.ports,
    )
    session.add(scan)
    await session.commit()
    await session.refresh(scan)

    enqueue(scan.id, target.host, scan.scan_type, scan.ports)
    return scan


@router.get("", response_model=list[ScanOut])
async def list_scans(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(Scan).order_by(Scan.id.desc())
    if user.role not in ("admin", "analyst"):
        query = query.where(Scan.created_by == user.id)
    result = await session.scalars(query)
    return list(result.all())


@router.get("/{scan_id}", response_model=ScanResultOut)
async def get_scan(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scan = await session.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сканування не знайдено")
    if scan.created_by != user.id and user.role not in ("admin", "analyst"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сканування не знайдено")
    return scan
