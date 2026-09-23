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