"""Сумативний ризик активу: скоринг по власних скануваннях.

Актив не має колонки з ризиком — він рахується з `scans`, які до нього
прив'язані. Питання лише в тому, що саме показувати: «поточний» стан дає
останнє завершене сканування (старі знахідки могли вже закрити), а «історичний
максимум» не дає забути, що колись актив був уразливий. Тому повертаємо обидва.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SCAN_DONE, Scan
from app.services.analysis import risk_level_from_score


class AssetRisk(TypedDict):
    risk_score: int | None
    risk_level: str | None
    max_risk_score: int | None
    max_risk_level: str | None
    scans_count: int
    last_scan_at: datetime | None


EMPTY_RISK: AssetRisk = {
    "risk_score": None,
    "risk_level": None,
    "max_risk_score": None,
    "max_risk_level": None,
    "scans_count": 0,
    "last_scan_at": None,
}


async def risk_by_asset(
    session: AsyncSession, asset_ids: Sequence[int]
) -> dict[int, AssetRisk]:
    """Агрегований ризик для списку активів (два запити, без N+1).

    Рахується по всіх скануваннях активу, а не лише власних: сканувати чужий
    актив не можна, але аналітик з іншої команди бачить усі сканування так
    само, як і сам власник.
    """
    ids = [asset_id for asset_id in asset_ids if asset_id]
    if not ids:
        return {}

    # count(*) — усі сканування (і failed теж), max(risk_score) ігнорує NULL,
    # тобто враховує лише завершені; max(finished_at) — остання спроба.
    totals = await session.execute(
        select(
            Scan.asset_id,
            func.count().label("scans_count"),
            func.max(Scan.risk_score).label("max_risk_score"),
            func.max(Scan.finished_at).label("last_scan_at"),
        )
        .where(Scan.asset_id.in_(ids))
        .group_by(Scan.asset_id)
    )

    result: dict[int, AssetRisk] = {}
    for asset_id, scans_count, max_risk, last_scan_at in totals.all():
        result[asset_id] = {
            "risk_score": None,
            "risk_level": None,
            "max_risk_score": max_risk,
            "max_risk_level": risk_level_from_score(max_risk) if max_risk is not None else None,
            "scans_count": scans_count or 0,
            "last_scan_at": last_scan_at,
        }

    # Поточний ризик — з останнього завершеного сканування. row_number()
    # замість «максимум id»: скан може бути перезапущений/виправлений пізніше
    # за нижчим id, і тоді найсвіжіший стан не той, що з найбільшим id.
    latest = (
        select(
            Scan.asset_id.label("asset_id"),
            Scan.risk_score.label("risk_score"),
            func.row_number()
            .over(
                partition_by=Scan.asset_id,
                order_by=(Scan.finished_at.desc(), Scan.id.desc()),
            )
            .label("row_number"),
        )
        .where(Scan.status == SCAN_DONE, Scan.asset_id.in_(ids))
        .subquery()
    )
    newest = await session.execute(
        select(latest.c.asset_id, latest.c.risk_score).where(latest.c.row_number == 1)
    )
    for asset_id, risk_score in newest.all():
        entry = result.get(asset_id)
        if entry is None:
            continue
        entry["risk_score"] = risk_score
        entry["risk_level"] = (
            risk_level_from_score(risk_score) if risk_score is not None else None
        )
    return result
