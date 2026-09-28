from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.scan import SCAN_TYPES


class ScanCreate(BaseModel):
    asset_id: int
    scan_type: str = Field(default="tcp")
    ports: str | None = Field(default=None, max_length=255)

    def validate_scan_type(self) -> bool:
        return self.scan_type in SCAN_TYPES


class ScanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    created_by: int
    status: str
    scan_type: str
    ports: str | None = None
    command: str | None = None
    error: str | None = None
    risk_score: int | None = None
    risk_level: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ScanResultOut(ScanOut):
    # Сирий XML навмисно не віддається тут: для -sV з NSE це сотні кілобайт на
    # кожне відкриття сторінки. Див. GET /api/v1/scans/{id}/raw.
    result: dict[str, Any] | None = None


class ScanRawOut(BaseModel):
    """Метадані архіву сирого nmap-XML + розпарсений «deep»-результат.

    xml не віддається, якщо він більший за scan_raw_xml_max_chars: обрізаний
    XML невалидний і вводить в оману, краще одразу запропонувати завантаження.
    """

    scan_id: int
    available: bool
    size_bytes: int = 0
    sha256: str = ""
    nmap_version: str = ""
    nmap_args: str = ""
    hosts_count: int = 0
    truncated: bool = False
    compressed: bool = False
    xml: str | None = None
    parsed: dict[str, Any] | None = None


class ScanRiskOut(BaseModel):
    scan_id: int
    risk_score: int
    risk_level: str
    services_count: int
    findings_by_severity: dict[str, int]
