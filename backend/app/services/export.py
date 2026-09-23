from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from fpdf import FPDF

from app.models.report import Report

FONT_DIR = Path(__file__).resolve().parents[1] / "assets"
BUNDLED_FONT = FONT_DIR / "DejaVuSans.ttf"


def _findings_rows(report: Report) -> list[list[Any]]:
    content = report.content
    asset = content.get("asset") or {}
    rows: list[list[Any]] = []
    asset_host = asset.get("host", "")
    for scan in content.get("scans", []):
        for finding in scan.get("findings", []):
            rows.append(
                [
                    scan.get("id"),
                    scan.get("scan_type"),
                    asset_host,
                    finding.get("service"),
                    finding.get("severity"),
                    finding.get("cve") or "",
                    finding.get("title"),
                    finding.get("recommendation"),
                ]
            )
    return rows


_CSV_HEADERS = [
    "scan_id",
    "scan_type",
    "host",
    "service",
    "severity",
    "cve",
    "title",
    "recommendation",
]


def report_to_csv(report: Report) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADERS)
    writer.writerows(_findings_rows(report))
    return buffer.getvalue()


def _escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def report_to_html(report: Report) -> str:
    content = report.content
    summary = content.get("summary", {})
    cards = "".join(
        f'<div class="card"><b>{_escape(value)}</b><span>{label}</span></div>'
        for label, value in (
            ("Сканувань", summary.get("total_scans", 0)),
            ("Findings", summary.get("total_findings", 0)),
            ("Високий/критичний ризик", summary.get("high_risk_scans", 0)),
        )
    )
    asset = content.get("asset")
    asset_line = ""
    if asset:
        parts = " · ".join(
            str(asset.get(k)) for k in ("name", "host", "kind") if asset.get(k) is not None
        )
        asset_line = f'<p class="muted">{_escape(parts)}</p>'
    scans_html = []
    for scan in content.get("scans", []):
        services = "".join(
            f'<tr><td>{s.get("port")}/{s.get("protocol")}</td>'
            f'<td>{_escape(s.get("service"))}</td>'
            f'<td>{_escape(s.get("product"))}</td>'
            f'<td>{_escape(s.get("version"))}</td></tr>'
            for s in scan.get("services", [])
        )
        findings = "".join(
            f'<tr><td>{_escape(f.get("severity"))}</td>'
            f'<td>{_escape(f.get("cve") or "")}</td>'
            f'<td>{_escape(f.get("title"))}</td></tr>'
            for f in scan.get("findings", [])
        )
        scans_html.append(
            f'<section class="scan"><h3>Скан #{scan.get("id")} · '
            f'{_escape(scan.get("scan_type"))} · {_escape(scan.get("status"))} · '
            f'ризик <span class="pill">{_escape(scan.get("risk_level") or "—")}</span></h3>'
            f'<h4>Сервіси</h4><table><thead><tr><th>Порт</th><th>Сервіс</th>'
            f'<th>Продукт</th><th>Версія</th></tr></thead>'
            f'<tbody>{services or '<tr><td colspan="4">—</td></tr>'}</tbody></table>'
            f'<h4>Findings</h4><table><thead><tr><th>Severity</th><th>CVE</th>'
            f'<th>Опис</th></tr></thead>'
            f'<tbody>{findings or '<tr><td colspan="3">—</td></tr>'}</tbody></table>'
            f'</section>'
        )
    scans_block = "".join(scans_html) or '<p class="muted">Немає сканувань</p>'
    return f"""<!DOCTYPE html>
<html lang="uk"><head><meta charset="utf-8"><title>{_escape(content.get("title"))}</title>
<style>
  body {{ font: 14px/1.5 system-ui, sans-serif; margin: 24px; color: #1c1e26; }}
  h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; }}
  .cards {{ display: flex; gap: 12px; margin: 16px 0; }}
  .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; }}
  .card b {{ font-size: 24px; display: block; }} .card span {{ color: #666; }}
  .muted {{ color: #666; }}
  table {{ border-collapse: collapse; width: 100%; margin: 6px 0 16px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
  .scan {{ border-top: 2px solid #999; margin-top: 14px; }}
  .pill {{ background: #eee; padding: 2px 8px; border-radius: 999px; }}
</style></head><body>
<h1>{_escape(content.get("title"))}</h1>
<p class="muted">Згенеровано: {_escape(content.get("generated_at"))}</p>
{asset_line}
<div class="cards">{cards}</div>
<h2>Сканування</h2>
{scans_block}
</body></html>"""


def report_to_pdf(report: Report) -> bytes:
    content = report.content
    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    if BUNDLED_FONT.exists():
        pdf.add_font("DejaVu", "", str(BUNDLED_FONT))
        pdf.set_font("DejaVu", "", 14)
    pdf.cell(0, 10, str(content.get("title", "Report")), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 7, f"Згенеровано: {content.get('generated_at')}", new_x="LMARGIN", new_y="NEXT")
    asset = content.get("asset")
    if asset:
        pdf.cell(
            0, 7,
            f"Актив: {asset.get('name')} · {asset.get('host')} · {asset.get('kind')}",
            new_x="LMARGIN", new_y="NEXT",
        )
    summary = content.get("summary", {})
    pdf.cell(
        0, 7,
        f"Підсумок: сканувань={summary.get('total_scans', 0)}, "
        f"findings={summary.get('total_findings', 0)}, "
        f"високий ризик={summary.get('high_risk_scans', 0)}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(2)
    for scan in content.get("scans", []):
        pdf.cell(
            0, 7,
            f"Скан #{scan.get('id')} ({scan.get('scan_type')}, {scan.get('status')}, "
            f"ризик {scan.get('risk_level') or '—'})",
            new_x="LMARGIN", new_y="NEXT",
        )
        for service in scan.get("services", []):
            pdf.cell(
                0, 6,
                f"  сервіс: {service.get('port')}/{service.get('protocol')} "
                f"{service.get('service')} {service.get('product')} {service.get('version')}",
                new_x="LMARGIN", new_y="NEXT",
            )
        for finding in scan.get("findings", []):
            pdf.cell(
                0, 6,
                f"  finding [{finding.get('severity')}] {finding.get('cve') or ''} "
                f"{finding.get('title')}",
                new_x="LMARGIN", new_y="NEXT",
            )
        pdf.ln(2)
    return bytes(pdf.output())