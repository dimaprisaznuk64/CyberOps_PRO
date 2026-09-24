from __future__ import annotations

from pydantic import BaseModel


class AIExplanationOut(BaseModel):
    provider: str
    explanation: str
    impact: str
    risk_explanation: str
    remediation: str