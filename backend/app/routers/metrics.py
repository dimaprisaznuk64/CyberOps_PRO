from __future__ import annotations

from fastapi import APIRouter, Response

from app.services.metrics import render_metrics

router = APIRouter(tags=["metrics"])

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics")
async def metrics():
    return Response(content=render_metrics(), media_type=METRICS_CONTENT_TYPE)