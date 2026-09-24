from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import app.models  # noqa: F401  (реєстрація всіх моделей для SQLAlchemy mapper)
from app.config import settings
from app.models.finding import Finding
from app.models.notification import Notification
from app.models.scan import SCAN_DONE, SCAN_FAILED, SCAN_RUNNING, Scan
from app.models.service import Service
from app.services.analysis import (
    compute_risk_score,
    derive_findings,
    extract_open_services,
    risk_level_from_score,
)
from app.services.events import publish_event
from app.services.metrics import (
    scan_duration_seconds,
    scan_results_total,
    scan_services_total,
)
from app.services.realtime import (
    MESSAGE_NOTIFICATION_CREATED,
    MESSAGE_SCAN_COMPLETED,
)
from app.services.realtime import (
    publish_event as publish_realtime_event,
)
from app.services.tracing import get_tracer
from celery import signals
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from services.scanner.nmap_runner import NmapError, build_command, parse_nmap_xml, run_nmap
from workers.celery_app import celery_app, serve_metrics

# Celery виконує кожен таск у власному event loop (asyncio.run), тому пул
# з'єднань не можна перевикористовувати між тасками. NullPool закриває
# з'єднання після кожного використання -> немає "Task attached to a different loop".
_worker_engine = create_async_engine(
    settings.database_url, poolclass=NullPool, future=True
)
SessionLocal = async_sessionmaker(
    _worker_engine, expire_on_commit=False, class_=AsyncSession
)


@signals.worker_ready.connect
def _start_metrics_server(*_args, **_kwargs) -> None:
    serve_metrics()


@celery_app.task(name="workers.tasks.run_scan")
def run_scan(scan_id: int, host: str, scan_type: str, ports: str | None) -> dict:
    return asyncio.run(_run_scan(scan_id, host, scan_type, ports))


async def _run_scan(
    scan_id: int, host: str, scan_type: str, ports: str | None
) -> dict:
    tracer = get_tracer("workers.tasks")
    span = tracer.start_span(
        "scan.run",
        attributes={"scan.id": scan_id, "scan.host": host, "scan.type": scan_type},
    )
    command = build_command(host, scan_type, ports)
    started_at = datetime.now(UTC)
    async with SessionLocal() as session:
        await session.execute(
            update(Scan)
            .where(Scan.id == scan_id)
            .values(
                status=SCAN_RUNNING,
                command=" ".join(command),
                started_at=started_at,
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
        span.set_attribute("scan.outcome", "failed")
        span.set_attribute("scan.error", str(exc))
        span.end()
        scan_results_total.labels(status=SCAN_FAILED, risk_level="none").inc()
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

    services = extract_open_services(parsed)
    findings = derive_findings(services)
    risk_score = compute_risk_score(findings)
    risk_level = risk_level_from_score(risk_score)

    async with SessionLocal() as session:
        scan = await session.get(Scan, scan_id)
        await session.execute(delete(Finding).where(Finding.scan_id == scan_id))
        await session.execute(delete(Service).where(Service.scan_id == scan_id))
        service_rows = [Service(scan_id=scan_id, **svc) for svc in services]
        session.add_all(service_rows)
        await session.flush()

        raised_findings: list[dict] = []
        for item in findings:
            session.add(
                Finding(
                    scan_id=scan_id,
                    service_id=service_rows[item["service_index"]].id,
                    severity=item["severity"],
                    title=item["title"],
                    description=item["description"],
                    recommendation=item["recommendation"],
                    cve=item["cve"],
                )
            )
            if item["severity"] in ("high", "critical"):
                raised_findings.append(item)

        await session.execute(
            update(Scan)
            .where(Scan.id == scan_id)
            .values(
                status=SCAN_DONE,
                raw_xml=xml_text,
                result=parsed,
                risk_score=risk_score,
                risk_level=risk_level,
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()

        created_notifications = []
        if scan is not None:
            done_notification = Notification(
                user_id=scan.created_by,
                scan_id=scan_id,
                title="Сканування завершено",
                body=f"{host} · {scan_type} · ризик {risk_score}/100 ({risk_level})",
                severity=risk_level.lower(),
            )
            session.add(done_notification)
            created_notifications.append(done_notification)
            if raised_findings:
                alert_notification = Notification(
                    user_id=scan.created_by,
                    scan_id=scan_id,
                    title="Виявлено знахідки високої/критичної важливості",
                    body="; ".join(f["title"] for f in raised_findings[:5]),
                    severity="critical",
                )
                session.add(alert_notification)
                created_notifications.append(alert_notification)
            await session.commit()

    duration = max((datetime.now(UTC) - started_at).total_seconds(), 0)
    scan_duration_seconds.labels(scan_type=scan_type).observe(duration)
    scan_results_total.labels(status=SCAN_DONE, risk_level=risk_level).inc()
    scan_services_total.labels(scan_type=scan_type).inc(len(services))
    span.set_attribute("scan.risk_score", risk_score)
    span.set_attribute("scan.risk_level", risk_level)
    span.set_attribute("scan.outcome", "done")
    span.end()

    user_id = scan.created_by if scan is not None else None
    await publish_realtime_event(
        user_id,
        MESSAGE_SCAN_COMPLETED,
        {
            "scan_id": scan_id,
            "status": SCAN_DONE,
            "risk_score": risk_score,
            "risk_level": risk_level,
        },
    )
    for notification in created_notifications:
        await publish_realtime_event(
            user_id,
            MESSAGE_NOTIFICATION_CREATED,
            {
                "notification_id": notification.id,
                "title": notification.title,
                "severity": notification.severity,
            },
        )

    publish_event(
        "scan.completed",
        {
            "scan_id": scan_id,
            "status": SCAN_DONE,
            "risk_score": risk_score,
            "risk_level": risk_level,
        },
    )
    for finding in raised_findings:
        publish_event(
            "finding.raised",
            {
                "scan_id": scan_id,
                "severity": finding["severity"],
                "title": finding["title"],
            },
        )
    return {"scan_id": scan_id, "status": SCAN_DONE, "risk_score": risk_score}
