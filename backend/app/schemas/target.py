from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str = Field(min_length=1, max_length=255)
    description: str | None = None


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class TargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    description: str | None = None
    owner_id: int
    created_at: datetime
