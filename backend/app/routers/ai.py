from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.dependencies import get_current_user
from app.models.finding import Finding
from app.models.scan import Scan
from app.models.user import User
from app.schemas.ai import AIExplanationOut
from app.services.ai_assistant import explain_finding

router = APIRouter(prefix="/api/v1/findings", tags=["ai-assistant"])


async def _get_finding_or_404(
    session: AsyncSession, finding_id: int, user: User
) -> Finding:
    query = select(Finding).options(selectinload(Finding.service)).where(Finding.id == finding_id)
    if user.role not in ("admin", "analyst"):
        query = query.join(Scan, Finding.scan_id == Scan.id).where(Scan.created_by == user.id)
    finding = await session.scalar(query)
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Знахідку не знайдено")
    return finding


@router.post("/{finding_id}/explain", response_model=AIExplanationOut)
async def explain_finding_endpoint(
    finding_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    finding = await _get_finding_or_404(session, finding_id, user)
    result = await explain_finding(finding)
    return {
        "provider": result.provider,
        "explanation": result.explanation,
        "impact": result.impact,
        "risk_explanation": result.risk_explanation,
        "remediation": result.remediation,
    }