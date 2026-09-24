from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import SessionLocal
from app.routers import audit, auth, health, metrics, users
from app.services.audit import audit_middleware
from app.services.logging_config import configure_logging, get_logger
from app.services.tracing import setup_tracing

configure_logging(settings.log_json)

logger = get_logger("auth_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_json)
    setup_tracing(app)
    logger.info("auth_service_started", extra={"version": app.version})
    yield


app = FastAPI(
    title="CyberOps Auth Service",
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
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(audit.router)