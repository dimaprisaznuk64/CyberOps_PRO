from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetKind = Literal["ip", "domain", "hostname", "docker"]


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    kind: AssetKind = "ip"
    docker_container: str | None = Field(default=None, max_length=255)
    description: str | None = None


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    kind: AssetKind | None = None
    docker_container: str | None = Field(default=None, max_length=255)
    description: str | None = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    kind: str
    docker_container: str | None = None
    description: str | None = None
    owner_id: int
    created_at: datetime

    # Агрегований ризик рахується з scans активу (app/services/asset_risk.py),
    # а не зберігається в активі: null = ще не було завершених сканувань.
    risk_score: int | None = None
    risk_level: str | None = None
    max_risk_score: int | None = None
    max_risk_level: str | None = None
    scans_count: int = 0
    last_scan_at: datetime | None = None