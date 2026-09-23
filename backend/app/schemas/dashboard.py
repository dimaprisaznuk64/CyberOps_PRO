from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    status: str
    scan_type: str
    risk_score: int | None = None
    risk_level: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class DashboardStats(BaseModel):
    unread_notifications: int
    total_assets: int
    high_risk_scans: int
    recent_scans: list[ScanBrief]