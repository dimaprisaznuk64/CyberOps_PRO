from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.reports import REPORT_TYPES


class ReportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    report_type: str
    asset_id: int | None = None
    scan_id: int | None = None

    def validate_report_type(self) -> bool:
        return self.report_type in REPORT_TYPES


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    report_type: str
    created_by: int
    asset_id: int | None = None
    scan_id: int | None = None
    created_at: datetime


class ReportDetailOut(ReportOut):
    content: dict[str, Any]