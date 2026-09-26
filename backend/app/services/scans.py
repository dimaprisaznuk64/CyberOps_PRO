from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import SCAN_FAILED, SCAN_PENDING, SCAN_RUNNING, Scan

STALE_ERROR = "Сканування зависло: воркер не завершив таск (перевірте логи worker)"


async def mark_enqueue_failed(session: AsyncSession, scan_id: int, reason: str) -> None:
    """Скан уже записано в БД, але поставити таск у чергу не вдалося.

    Без цього рядок лишався б назавжди в pending: клієнт бачить «обробку», а
    її не буде ніколи — треба або змінити статус, або видалити рядок.
    """
    await session.execute(
        update(Scan)
        .where(Scan.id == scan_id)
        .values(status=SCAN_FAILED, error=reason, finished_at=datetime.now(UTC))
    )
    await session.commit()


async def fail_stale_scans(
    session: AsyncSession,
    *,
    stale_after_seconds: int,
    now: datetime | None = None,
) -> list[int]:
    """Переводить завислі `pending`/`running` у `failed`.

    Потрібно для випадків, коли таск у чергу потрапив, але воркер упав або був
    убитий (OOM, рестарт контейнера) — інакше скан світиться «в обробці»
    вічно. Повертає id змінених сканів.
    """
    moment = now or datetime.now(UTC)
    # для running орієнтир — старт, для pending — створення
    deadline = moment - timedelta(seconds=stale_after_seconds)

    result = await session.execute(
        select(Scan.id).where(
            Scan.status.in_((SCAN_PENDING, SCAN_RUNNING)),
            Scan.finished_at.is_(None),
        )
    )
    candidates = list(result.scalars())

    stale: list[int] = []
    for scan_id in candidates:
        scan = await session.get(Scan, scan_id)
        if scan is None:
            continue
        reference = scan.started_at or scan.created_at
        if reference is None:
            continue
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        if reference <= deadline:
            stale.append(scan_id)

    if not stale:
        return []

    await session.execute(
        update(Scan)
        .where(Scan.id.in_(stale))
        .values(status=SCAN_FAILED, error=STALE_ERROR, finished_at=moment)
    )
    await session.commit()
    return stale
