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
    result: dict[str, Any] | None = None
    raw_xml: str | None = None


class ScanRiskOut(BaseModel):
    scan_id: int
    risk_score: int
    risk_level: str
    services_count: int
    findings_by_severity: dict[str, int]
