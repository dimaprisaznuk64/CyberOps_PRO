"""Тести початкового налаштування адміністратора.

Цей механізм закриває P2: `ADMIN_USERNAME`/`ADMIN_PASSWORD` існували в
конфігурації з v1.2, але нікуди не читались, тож на свіжій базі таблиця
`users` була порожньою. Оскільки публічна реєстрація не дозволяє підняти
роль (див. `test_users.py::test_register_ignores_any_role`), ескалація через
register залишалася єдиним способом отримати адміна.

Тому тест на сівач — не тест «зручності», а тест того, що в системі взагалі
існує легітимний шлях в адмінку.
"""

from __future__ import annotations

from app.auth_app import seed_admin_with_retry
from app.config import settings
from app.models.user import ROLE_ADMIN, ROLE_USER, User
from app.services.auth import authenticate, hash_password
from app.services.seed import ensure_admin_user
from sqlalchemy import func, select


async def test_seed_creates_admin(session_factory):
    created = await ensure_admin_user(session_factory)
    assert created is True

    async with session_factory() as session:
        admin = await authenticate(session, settings.admin_username, settings.admin_password)
        assert admin is not None
        assert admin.role == ROLE_ADMIN


async def test_seed_is_idempotent(session_factory):
    """Другий виклик не створює дубль і не ламає стан."""
    assert await ensure_admin_user(session_factory) is True
    assert await ensure_admin_user(session_factory) is False

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(User).where(User.username == settings.admin_username)
        )
        assert count == 1


async def test_seed_never_overwrites_changed_password(session_factory):
    """Пароль існуючого адміна не перезаписується.

    Якби перезаписувався, кожен рестарт контейнера повертав би пароль, який
    адмін змінив через UI, — на публічному інстансі це означало б, що
    «змінив пароль» не має жодного ефекту.
    """
    async with session_factory() as session:
        session.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password("already-changed-by-hand"),
                role=ROLE_ADMIN,
            )
        )
        await session.commit()

    assert await ensure_admin_user(session_factory) is False

    async with session_factory() as session:
        # старий пароль з конфігурації більше не працює...
        assert await authenticate(
            session, settings.admin_username, settings.admin_password
        ) is None
        # ...а той, який задали вручну, працює
        assert (
            await authenticate(session, settings.admin_username, "already-changed-by-hand")
            is not None
        )


async def test_seed_does_not_promote_existing_plain_user(session_factory):
    """Наявного звичайного користувача конфігурація до адміна не піднімає.

    Інакше достатньо було б зареєструватися під іменем, яке є в ADMIN_USERNAME,
    і дочекатися рестарту, щоб отримати адміна.
    """
    async with session_factory() as session:
        session.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password("someone-got-here-first"),
                role=ROLE_USER,
            )
        )
        await session.commit()

    assert await ensure_admin_user(session_factory) is False

    async with session_factory() as session:
        user = await session.scalar(
            select(User).where(User.username == settings.admin_username)
        )
        assert user.role == ROLE_USER


async def test_seed_retries_until_database_is_ready(monkeypatch, session_factory):
    """Сид має дожидатися міграцій, а не падати один раз назавжди.

    Регресія, знайдена на kind: pod auth піднімається одночасно з міграціями,
    тож на свіжому кластері таблиці users ще немає. Помилку ковтали, а
    розраховували на «наступний рестарт добере решту» — але рестарту не
    було: контейнер жив далі, адміністратора не існувало, і ніхто не міг
    увійти. Усі поді were Running, а система не працювала.
    """
    calls = 0
    real = ensure_admin_user

    async def flaky(_factory):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise RuntimeError("relation \"users\" does not exist")
        # Саме test-ова фабрика, а не та, що її передає seed_admin_with_retry:
        # інакше пішли б у справжню БД із налаштувань застосунку.
        return await real(session_factory)

    monkeypatch.setattr("app.auth_app.ensure_admin_user", flaky)
    monkeypatch.setattr("app.auth_app.SEED_RETRY_DELAYS", (0, 0))

    assert await seed_admin_with_retry() is True
    assert calls == 3, "має повторити спробу після помилки, а не здатися"


async def test_seed_gives_up_after_last_attempt(monkeypatch):
    """Система має сказати вголос, що адміністратора так і не створили.

    Інакше на стенді без адміна тихо, і наступна сесія знову шукатиме
    причину, не знаходячи її в логах.
    """
    calls = 0

    async def always_fails(_factory):
        nonlocal calls
        calls += 1
        raise RuntimeError("connection refused")

    monkeypatch.setattr("app.auth_app.ensure_admin_user", always_fails)
    monkeypatch.setattr("app.auth_app.SEED_RETRY_DELAYS", (0, 0))

    assert await seed_admin_with_retry() is False
    assert calls == 3, "усі спроби мають бути використані перед здачею"


async def test_seed_does_not_retry_when_admin_already_exists(monkeypatch, session_factory):
    """Готовий адмін — не привід для повторів: пароль не перезаписується."""
    calls = 0
    real = ensure_admin_user

    async def counting(_factory):
        nonlocal calls
        calls += 1
        return await real(session_factory)

    monkeypatch.setattr("app.auth_app.ensure_admin_user", counting)
    monkeypatch.setattr("app.auth_app.SEED_RETRY_DELAYS", (0, 0))

    assert await ensure_admin_user(session_factory) is True
    assert await seed_admin_with_retry() is False
    assert calls == 1, "успішна спроба має завершувати цикл одразу"
