from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.user import ROLE_ADMIN, User
from app.services.auth import hash_password
from app.services.logging_config import get_logger

logger = get_logger("auth_service")


async def ensure_admin_user(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    """Створює початкового адміністратора, якщо його ще немає.

    Навіщо це взагалі існує: публічна реєстрація не дозволяє підняти роль
    (див. `routers/auth.register`), тому без цього механізму в системі не було б
    жодного легітимного способу отримати адміна — єдиним шляхом лишалася б
    ескалація через register.

    Найважливіша властивість — ідемпотентність. Пароль існуючого адміна ніколи
    не перезаписується: інакше кожен рестарт контейнера скидав би пароль, який
    адмін змінив через UI, і на публічному інстансі «змінив — і забув» означало
    б повернення до початкового пароля.

    Повертає True, якщо користувача створено цього разу.
    """
    username = settings.admin_username
    password = settings.admin_password

    if not username or not password:
        logger.warning("admin_seed_skipped_empty_credentials")
        return False

    async with session_factory() as session:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing is not None:
            if existing.role != ROLE_ADMIN:
                # Не піднімаємо наявного користувача до адміна: можливо, це
                # зареєстрований через публічний ендпойт. Підняття ролі —
                # операція з консолі адміністратора, а не наслідок конфігурації.
                logger.warning(
                    "admin_seed_conflict",
                    extra={
                        "username": username,
                        "role": existing.role,
                        "reason": "user exists with non-admin role, left untouched",
                    },
                )
            else:
                logger.info("admin_seed_noop", extra={"username": username})
            return False

        session.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=ROLE_ADMIN,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # Два репліки auth піднімаються одночасно — перемога дісталася не
            # тій, хто вставив першим. Це не помилка: бажаний стан досягнуто.
            await session.rollback()
            logger.info("admin_seed_raced", extra={"username": username})
            return False

    logger.info("admin_seed_created", extra={"username": username})
    return True
