from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.config import settings
from app.database import SessionLocal
from app.models.scan import SCAN_DONE, SCAN_FAILED, SCAN_RUNNING, Scan
from sqlalchemy import update

from services.scanner.nmap_runner import NmapError, build_command, parse_nmap_xml, run_nmap
from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.run_scan")
def run_scan(scan_id: int, host: str, scan_type: str, ports: str | None) -> dict:
    return asyncio.run(_run_scan(scan_id, host, scan_type, ports))


async def _run_scan(
    scan_id: int, host: str, scan_type: str, ports: str | None
) -> dict:
    command = build_command(host, scan_type, ports)
    async with SessionLocal() as session:
        await session.execute(
            update(Scan)
            .where(Scan.id == scan_id)
            .values(
                status=SCAN_RUNNING,
                command=" ".join(command),
                started_at=datetime.now(UTC),
                error=None,
            )
        )
        await session.commit()

    try:
        xml_text = await asyncio.to_thread(
            run_nmap, command, settings.nmap_timeout_seconds
        )
        parsed = parse_nmap_xml(xml_text)
    except NmapError as exc:
        async with SessionLocal() as session:
            await session.execute(
                update(Scan)
                .where(Scan.id == scan_id)
                .values(
                    status=SCAN_FAILED,
                    error=str(exc),
                    finished_at=datetime.now(UTC),
                )
            )
            await session.commit()
        return {"scan_id": scan_id, "status": SCAN_FAILED, "error": str(exc)}

    async with SessionLocal() as session:
        await session.execute(
            update(Scan)
            .where(Scan.id == scan_id)
            .values(
                status=SCAN_DONE,
                raw_xml=xml_text,
                result=parsed,
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()
    return {"scan_id": scan_id, "status": SCAN_DONE}
