from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import SessionLocal
from app.routers import (
    ai,
    assets,
    dashboard,
    findings,
    health,
    metrics,
    notifications,
    reports,
    scans,
    ws,
)
from app.services.audit import audit_middleware
from app.services.logging_config import configure_logging, get_logger
from app.services.realtime import manager, run_event_listener
from app.services.tracing import setup_tracing

# Стара статична сторінка-дашборд (legacy/dashboard/index.html). Напряму
# монтувати frontend/ не можна: gateway не вимагає токен для /dashboard, тож
# так у публічний доступ потрапили б усі файли каталогу — node_modules,
# .env.example, next.config.mjs, .next.
LEGACY_DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "legacy" / "dashboard"

configure_logging(settings.log_json)

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_json)
    setup_tracing(app)
    if settings.realtime_mode == "memory":
        await manager.start()
        app.state.realtime_task = getattr(manager, "_task", None)
    else:
        app.state.realtime_task = asyncio.create_task(run_event_listener())
    logger.info("application_started", extra={"version": app.version})
    yield
    task = getattr(app.state, "realtime_task", None)
    if task is not None:
        task.cancel()


app = FastAPI(
    title="CyberOps Core Service",
    version="0.7.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.audit_session_factory = SessionLocal
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_middleware)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(assets.router)
app.include_router(scans.router)
app.include_router(findings.router)
app.include_router(ai.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(ws.router)

if LEGACY_DASHBOARD_DIR.is_dir():
    app.mount(
        "/dashboard",
        StaticFiles(directory=LEGACY_DASHBOARD_DIR, html=True),
        name="dashboard",
    )
else:
    # Не критично: основний UI — це Next.js. Не падаємо на imports, щоб
    # скорочений образ без legacy міг підніматись.
    logger.warning("legacy_dashboard_missing", extra={"path": str(LEGACY_DASHBOARD_DIR)})
