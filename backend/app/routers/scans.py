from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, require_analyst
from app.models.asset import Asset
from app.models.finding import Finding
from app.models.scan import SCAN_PENDING, Scan
from app.models.service import Service
from app.models.user import User
from app.schemas.scan import ScanCreate, ScanOut, ScanResultOut, ScanRiskOut
from app.schemas.service import ServiceOut
from app.services.netguard import HostNotAllowedError, assert_host_allowed
from app.tasks import get_task_enqueuer

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


async def _get_scan_or_404(scan_id: int, user: User, session: AsyncSession) -> Scan:
    scan = await session.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сканування не знайдено")
    if scan.created_by != user.id and user.role not in ("admin", "analyst"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сканування не знайдено")
    return scan


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
    asset = await session.get(Asset, payload.asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Актив не знайдено")
    if asset.kind != "docker":
        try:
            assert_host_allowed(asset.host)
        except HostNotAllowedError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    scan = Scan(
        asset_id=asset.id,
        created_by=_.id,
        status=SCAN_PENDING,
        scan_type=payload.scan_type,
        ports=payload.ports,
    )
    session.add(scan)
    await session.commit()
    await session.refresh(scan)

    enqueue(scan.id, asset.host, scan.scan_type, scan.ports)
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
    return await _get_scan_or_404(scan_id, user, session)


@router.get("/{scan_id}/services", response_model=list[ServiceOut])
async def list_scan_services(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scan = await _get_scan_or_404(scan_id, user, session)
    result = await session.scalars(
        select(Service).where(Service.scan_id == scan.id).order_by(Service.port)
    )
    return list(result.all())


@router.get("/{scan_id}/risk", response_model=ScanRiskOut)
async def get_scan_risk(
    scan_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scan = await _get_scan_or_404(scan_id, user, session)
    findings = (
        await session.scalars(select(Finding).where(Finding.scan_id == scan.id))
    ).all()
    services_count = await session.scalar(
        select(func.count()).select_from(Service).where(Service.scan_id == scan.id)
    )
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return ScanRiskOut(
        scan_id=scan.id,
        risk_score=scan.risk_score or 0,
        risk_level=scan.risk_level or "LOW",
        services_count=services_count or 0,
        findings_by_severity=counts,
    )
