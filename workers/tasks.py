from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import app.models  # noqa: F401  (реєстрація всіх моделей для SQLAlchemy mapper)
from app.config import settings
from app.models.finding import Finding
from app.models.notification import (
    CHANNEL_WEB,
    EXTERNAL_CHANNELS,
    STATUS_PENDING,
    STATUS_SENT,
    Notification,
)
from app.models.scan import SCAN_DONE, SCAN_FAILED, SCAN_RUNNING, Scan
from app.models.service import Service
from app.models.user import User
from app.services.analysis import (
    compute_risk_score,
    derive_findings,
    extract_open_services,
    risk_level_from_score,
)
from app.services.events import publish_event
from app.services.metrics import (
    notifications_delivered_total,
    scan_duration_seconds,
    scan_results_total,
    scan_services_total,
)
from app.services.notifications import build_notifications, deliver, prefs_from_user
from app.services.raw_nmap import pack_raw_xml
from app.services.realtime import (
    MESSAGE_NOTIFICATION_CREATED,
    MESSAGE_SCAN_COMPLETED,
)
from app.services.realtime import (
    publish_event as publish_realtime_event,
)
from app.services.scans import fail_stale_scans
from app.services.tracing import extract_celery_context, get_tracer
from app.tasks import enqueue_notification_delivery
from celery import signals
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from services.scanner.nmap_runner import NmapError, build_command, parse_nmap_xml, run_nmap
from workers.celery_app import celery_app, serve_metrics

logger = logging.getLogger("worker")

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


@celery_app.task(name="workers.tasks.run_scan", bind=True)
def run_scan(
    self, scan_id: int, host: str, scan_type: str, ports: str | None
) -> dict:
    # bind=True заради self.request: без нього Celery робить з функції
    # staticmethod, і до повідомлення не дістатися — треба ж знати, який саме
    # traceparent прийшов.
    #
    # Батьківський context із повідомлення, щоб `scan.run` продовжив слід
    # запиту, що поставив скан у чергу, а не почав новий. Відсутність
    # контексту не є помилкою: тоді спан просто стане коренем.
    parent = extract_celery_context(self.request.headers)
    return asyncio.run(_run_scan(scan_id, host, scan_type, ports, parent=parent))


@celery_app.task(name="workers.tasks.reap_stale_scans")
def reap_stale_scans() -> dict:
    """Періодично (celery beat) переводить завислі скАНИ у failed.

    Рядок може залишитись у pending/running, якщо воркер упав під час таску
    або був убитий (OOM, рестарт контейнера) — тоді ніхто не оновить статус.
    """

    async def _reap() -> list[int]:
        async with SessionLocal() as session:
            return await fail_stale_scans(
                session, stale_after_seconds=settings.scan_stale_after_seconds
            )

    stale = asyncio.run(_reap())
    if stale:
        logger.warning("stale_scans_failed", extra={"count": len(stale), "ids": stale})
    return {"reaped": len(stale), "scan_ids": stale}


async def _run_scan(
    scan_id: int,
    host: str,
    scan_type: str,
    ports: str | None,
    parent: object | None = None,
) -> dict:
    tracer = get_tracer("workers.tasks")
    span = tracer.start_span(
        "scan.run",
        attributes={"scan.id": scan_id, "scan.host": host, "scan.type": scan_type},
        context=parent,
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
    # Сирий XML — найбільша частина результату, тож у базі лежить стиснутим.
    # pack_raw_xml() уже віддає готовий gzip-байт, а не контейнер: packed[0]
    # тут був би першим байтом (0x1f), і запис падав би навіть на валідних XML.
    packed, raw_size, raw_sha = pack_raw_xml(xml_text)

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
                raw_xml_gz=packed,
                raw_xml=None,
                result=parsed,
                risk_score=risk_score,
                risk_level=risk_level,
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()

        created_notifications = []
        external_rows: list[Notification] = []
        if scan is not None:
            owner = await session.get(User, scan.created_by)
            prefs = prefs_from_user(owner)
            events = [
                (
                    "Сканування завершено",
                    f"{host} · {scan_type} · ризик {risk_score}/100 ({risk_level})",
                    risk_level.lower(),
                )
            ]
            if raised_findings:
                events.append(
                    (
                        "Виявлено знахідки високої/критичної важливості",
                        "; ".join(f["title"] for f in raised_findings[:5]),
                        "critical",
                    )
                )
            for title, body, severity in events:
                rows = build_notifications(
                    user_id=scan.created_by,
                    scan_id=scan_id,
                    title=title,
                    body=body,
                    severity=severity,
                    prefs=prefs,
                )
                session.add_all(rows)
                created_notifications.extend(rows)
                external_rows.extend(r for r in rows if r.channel in EXTERNAL_CHANNELS)
            await session.commit()

    # id зовнішніх рядків з'являється лише після flush/commit, тому збираємо тут.
    # Доставка йде окремими тасками — SMTP/Telegram не блокують скан.
    for row in external_rows:
        if row.status == STATUS_PENDING and row.id is not None:
            enqueue_notification_delivery(row.id)

    duration = max((datetime.now(UTC) - started_at).total_seconds(), 0)
    scan_duration_seconds.labels(scan_type=scan_type).observe(duration)
    scan_results_total.labels(status=SCAN_DONE, risk_level=risk_level).inc()
    scan_services_total.labels(scan_type=scan_type).inc(len(services))
    span.set_attribute("scan.risk_score", risk_score)
    span.set_attribute("scan.risk_level", risk_level)
    span.set_attribute("scan.raw_xml_bytes", raw_size)
    span.set_attribute("scan.raw_xml_sha256", raw_sha)
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
        # зовнішні канали дублюють той самий заголовок — у стрічку йде тільки web
        if notification.channel != CHANNEL_WEB:
            continue
        await publish_realtime_event(
            user_id,
            MESSAGE_NOTIFICATION_CREATED,
            {
                "notification_id": notification.id,
                "title": notification.title,
                "severity": notification.severity,
                "channel": notification.channel,
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


@celery_app.task(name="workers.tasks.deliver_notification")
def deliver_notification(notification_id: int) -> dict:
    return asyncio.run(_deliver_notification(notification_id))


async def _deliver_notification(notification_id: int) -> dict:
    async with SessionLocal() as session:
        notification = await session.get(Notification, notification_id)
        if notification is None:
            return {"notification_id": notification_id, "status": "missing"}
        if notification.channel not in EXTERNAL_CHANNELS:
            return {"notification_id": notification_id, "status": "ignored"}
        if notification.status == STATUS_SENT:
            return {"notification_id": notification_id, "status": "already_sent"}

        result = await deliver(notification)
        notification.status = result.status
        notification.error = result.error
        notification.sent_at = datetime.now(UTC) if result.status == STATUS_SENT else None
        await session.commit()
        notifications_delivered_total.labels(
            channel=notification.channel, status=result.status
        ).inc()
        return {
            "notification_id": notification_id,
            "channel": notification.channel,
            "status": result.status,
            "error": result.error,
        }
