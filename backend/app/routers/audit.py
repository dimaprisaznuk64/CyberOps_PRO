from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import require_admin
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    user_id: int | None = None,
    method: str | None = None,
    path: str | None = None,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if method is not None:
        query = query.where(AuditLog.method == method)
    if path is not None:
        query = query.where(AuditLog.path.contains(path))
    result = await session.scalars(query)
    return list(result.all())