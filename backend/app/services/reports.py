from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.finding import Finding
from app.models.scan import Scan
from app.models.service import Service

REPORT_TYPE_ASSET = "asset"
REPORT_TYPE_SCAN = "scan"
REPORT_TYPES = (REPORT_TYPE_ASSET, REPORT_TYPE_SCAN)


def _findings_by_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    return counts


def _aggregate(entries: list[dict[str, Any]]) -> dict[str, Any]:
    total_findings = 0
    findings_by_severity: dict[str, int] = {}
    high_risk_scans = 0
    for entry in entries:
        total_findings += len(entry["findings"])
        for severity, count in _findings_by_severity(entry["findings"]).items():
            findings_by_severity[severity] = findings_by_severity.get(severity, 0) + count
        if entry.get("risk_level") in ("HIGH", "CRITICAL"):
            high_risk_scans += 1
    return {
        "total_scans": len(entries),
        "total_findings": total_findings,
        "findings_by_severity": findings_by_severity,
        "high_risk_scans": high_risk_scans,
    }


async def _scan_entries(
    session: AsyncSession, scans: list[Scan]
) -> list[dict[str, Any]]:
    scan_ids = [scan.id for scan in scans]
    services_rows = (
        await session.scalars(
            select(Service).where(Service.scan_id.in_(scan_ids)).order_by(Service.port)
        )
    ).all() if scan_ids else []
    findings_rows = (
        await session.scalars(
            select(Finding).where(Finding.scan_id.in_(scan_ids)).order_by(Finding.severity)
        )
    ).all() if scan_ids else []
    services_by_scan: dict[int, list[Any]] = {}
    service_by_id: dict[int, Any] = {}
    for service in services_rows:
        services_by_scan.setdefault(service.scan_id, []).append(service)
        service_by_id[service.id] = service
    findings_by_scan: dict[int, list[Any]] = {}
    for finding in findings_rows:
        findings_by_scan.setdefault(finding.scan_id, []).append(finding)

    return [
        {
            "id": scan.id,
            "scan_type": scan.scan_type,
            "status": scan.status,
            "risk_score": scan.risk_score,
            "risk_level": scan.risk_level,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
            "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
            "services": [
                {
                    "port": s.port,
                    "protocol": s.protocol,
                    "service": s.service,
                    "product": s.product,
                    "version": s.version,
                    "cpe": s.cpe,
                }
                for s in services_by_scan.get(scan.id, [])
            ],
            "findings": [
                {
                    "severity": f.severity,
                    "title": f.title,
                    "description": f.description,
                    "recommendation": f.recommendation,
                    "cve": f.cve,
                    "service": (
                        f"{service_by_id[f.service_id].service} "
                        f"{service_by_id[f.service_id].product or ''} "
                        f"{service_by_id[f.service_id].version or ''}"
                    ).strip()
                    if f.service_id in service_by_id
                    else None,
                }
                for f in findings_by_scan.get(scan.id, [])
            ],
        }
        for scan in scans
    ]


async def build_asset_report(
    session: AsyncSession, asset_id: int, title: str
) -> dict[str, Any]:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise ValueError("Актив не знайдено")
    scans = (
        await session.scalars(
            select(Scan).where(Scan.asset_id == asset_id).order_by(Scan.id.desc())
        )
    ).all()
    entries = await _scan_entries(session, scans)
    return {
        "title": title,
        "asset": {
            "id": asset.id,
            "name": asset.name,
            "host": asset.host,
            "kind": asset.kind,
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": _aggregate(entries),
        "scans": entries,
    }


async def build_scan_report(
    session: AsyncSession, scan_id: int, title: str
) -> dict[str, Any]:
    scan = await session.get(Scan, scan_id)
    if scan is None:
        raise ValueError("Сканування не знайдено")
    asset = await session.get(Asset, scan.asset_id)
    entries = await _scan_entries(session, [scan])
    return {
        "title": title,
        "asset": (
            {
                "id": asset.id,
                "name": asset.name,
                "host": asset.host,
                "kind": asset.kind,
            }
            if asset is not None
            else None
        ),
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": _aggregate(entries),
        "scans": entries,
    }