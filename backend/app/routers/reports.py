from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_current_user, require_analyst
from app.models.asset import Asset
from app.models.report import Report
from app.models.scan import Scan
from app.models.user import User
from app.schemas.report import ReportCreate, ReportDetailOut, ReportOut
from app.services.events import EventPublisher, get_publisher
from app.services.export import report_to_csv, report_to_html, report_to_pdf
from app.services.reports import (
    REPORT_TYPE_ASSET,
    REPORT_TYPE_SCAN,
    build_asset_report,
    build_scan_report,
)

EXPORT_FORMATS = ("csv", "html", "pdf")

_EXPORT_MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
}

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


async def _get_report_or_404(report_id: int, user: User, session: AsyncSession) -> Report:
    report = await session.get(Report, report_id)
    if report is None or (report.created_by != user.id and user.role not in ("admin", "analyst")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Звіт не знайдено")
    return report


async def _assert_report_target_allowed(
    session: AsyncSession,
    user: User,
    report_type: str,
    asset_id: int | None,
    scan_id: int | None,
) -> None:
    """Не дає будувати звіт за об'єктом, до якого користувач не має доступу.

    Раніше тут не було жодної перевірки: достатньо було знати ID чужого актива
    або сканування, і звіт збирався — разом із усіма сервісами, знахідками та
    ризиком цілі. Це класичний IDOR: ендпойнт приймав ID, а не об'єкт.

    Правила беремо ті самі, що в читанні, щоб модель ролей була послідовною:
    актив — за `owner_id`, сканування — за `created_by`. Аналітик і адмін
    бачать все, як у findings і scans. Відповідь 404, а не 403, щоб не
    підтверджувати існування об'єкта для того, хто не має до нього доступу.
    """
    if report_type == REPORT_TYPE_ASSET:
        if asset_id is None:
            return
        asset = await session.get(Asset, asset_id)
        if asset is None or (asset.owner_id != user.id and user.role != "admin"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Актив не знайдено")
        return

    if scan_id is None:
        return
    scan = await session.get(Scan, scan_id)
    if scan is None or (scan.created_by != user.id and user.role not in ("admin", "analyst")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Сканування не знайдено")


@router.post("", response_model=ReportDetailOut, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    _: User = Depends(require_analyst),
    session: AsyncSession = Depends(get_session),
    publisher: EventPublisher = Depends(get_publisher),
):
    if not payload.validate_report_type():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Невірний тип звіту (asset|scan)"
        )
    if payload.report_type == REPORT_TYPE_ASSET and payload.asset_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Потрібен asset_id")
    if payload.report_type == REPORT_TYPE_SCAN and payload.scan_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Потрібен scan_id")

    await _assert_report_target_allowed(
        session, _, payload.report_type, payload.asset_id, payload.scan_id
    )

    try:
        if payload.report_type == REPORT_TYPE_ASSET:
            content = await build_asset_report(session, payload.asset_id, payload.title)
        else:
            content = await build_scan_report(session, payload.scan_id, payload.title)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    report = Report(
        title=payload.title,
        report_type=payload.report_type,
        created_by=_.id,
        asset_id=payload.asset_id,
        scan_id=payload.scan_id,
        content=content,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)

    publisher.publish(
        "report.generated",
        {
            "report_id": report.id,
            "report_type": report.report_type,
            "created_by": report.created_by,
        },
    )
    return report


@router.get("", response_model=list[ReportOut])
async def list_reports(
    report_type: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(Report).order_by(Report.id.desc())
    if user.role not in ("admin", "analyst"):
        query = query.where(Report.created_by == user.id)
    if report_type is not None:
        query = query.where(Report.report_type == report_type)
    result = await session.scalars(query)
    return list(result.all())


@router.get("/{report_id}", response_model=ReportDetailOut)
async def get_report(
    report_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _get_report_or_404(report_id, user, session)


@router.get("/{report_id}/export")
async def export_report(
    report_id: int,
    format: str = "csv",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if format not in EXPORT_FORMATS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Формат має бути одним з: {', '.join(EXPORT_FORMATS)}",
        )
    report = await _get_report_or_404(report_id, user, session)
    if format == "csv":
        body: str | bytes = report_to_csv(report)
    elif format == "html":
        body = report_to_html(report)
    else:
        body = report_to_pdf(report)
    return Response(
        content=body,
        media_type=_EXPORT_MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="report_{report.id}.{format}"'},
    )