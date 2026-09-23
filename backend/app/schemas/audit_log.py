from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    method: str
    path: str
    status_code: int
    client_ip: str | None = None
    user_agent: str | None = None
    created_at: datetime