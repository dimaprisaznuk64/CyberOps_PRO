from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_id: int
    service_id: int | None = None
    severity: str
    title: str
    description: str | None = None
    recommendation: str | None = None
    cve: str | None = None
    created_at: datetime
