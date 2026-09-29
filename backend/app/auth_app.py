from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import SessionLocal
from app.routers import audit, auth, health, metrics, users
from app.services.audit import audit_middleware
from app.services.logging_config import configure_logging, get_logger
from app.services.seed import ensure_admin_user
from app.services.tracing import setup_tracing

configure_logging(settings.log_json)

logger = get_logger("auth_service")

# Паузи між спробами сівача. Найперша спроба — без паузи.
#
# Чому це взагалі потрібно: pod auth піднімається одночасно з міграціями
# (`kubectl apply -k` застосовує все відразу), тож на свіжому кластері БД ще
# без таблиці users і seed падає. Раніше помилку ковтали, а розраховували на
# «наступний рестарт добере решту» — але рестарту ніхто не робить: контейнер
# працює роками. Результат — стенд «здоровий», усі подні Running, а
# адміністратора немає і увійти неможливо (старий E2E з одним curl /health
# цього не бачив).
#
# Сума ≈127 с: достатньо для міграцій навіть на повільному CI-раннері, і
# при цьому не тримаємо сервіс у старті.
SEED_RETRY_DELAYS: tuple[int, ...] = (2, 5, 10, 20, 30, 30, 30)


async def seed_admin_with_retry() -> bool:
    """Сіє адміністратора, повторюючи спроби, доки БД не готова.

    Повертає True, якщо адміністратора створено цього разу, і False, якщо
    він уже був (або створити не вдалося за всі спроби).
    """
    attempts = len(SEED_RETRY_DELAYS) + 1
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            await asyncio.sleep(SEED_RETRY_DELAYS[attempt - 2])
        try:
            created = await ensure_admin_user(SessionLocal)
        except Exception:
            # Наступна спроба — attempt+1, тож її пауза лежить за індексом
            # attempt-1. Остання спроба пауз не має: next_delay=None.
            next_delay = (
                SEED_RETRY_DELAYS[attempt - 1] if attempt < attempts else None
            )
            logger.exception(
                "admin_seed_failed",
                extra={"attempt": attempt, "attempts": attempts, "next_delay_s": next_delay},
            )
            continue
        # Ключ не "created": це зарезервоване поле LogRecord (час створення
        # запису), і передача такого ключа в logging піднімає KeyError —
        # тобто впав би весь сид, а не просто не залогувався.
        logger.info(
            "admin_seed_done",
            extra={"attempt": attempt, "admin_created": created},
        )
        return created
    logger.error("admin_seed_gave_up", extra={"attempts": attempts})
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_json)
    setup_tracing(app)
    # Створює початкового адміністратора. Раніше його не існувало взагалі, а
    # публічна реєстрація не дозволяє підняти роль, тож легітимного входу
    # в адмінку не було — лише ескалація через register.
    #
    # У фоні й із повторами: старт сервісу не залежить від готовності БД, а
    # сид все одно відбудеться, щойно міграції завершаться.
    task = asyncio.create_task(seed_admin_with_retry())
    app.state.admin_seed_task = task
    logger.info("auth_service_started", extra={"version": app.version})
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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