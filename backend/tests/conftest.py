from __future__ import annotations

import pytest
import pytest_asyncio
from app.database import Base, get_session
from app.main import app
from app.models.user import User
from app.services.auth import hash_password
from app.services.events import CollectingPublisher, get_publisher
from app.tasks import get_task_enqueuer
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
def scan_queue():
    calls: list[tuple] = []

    def _enqueue(scan_id: int, host: str, scan_type: str, ports: str | None) -> None:
        calls.append((scan_id, host, scan_type, ports))

    _enqueue.calls = calls  # type: ignore[attr-defined]
    return _enqueue


@pytest.fixture
def event_publisher():
    publisher = CollectingPublisher()
    app.dependency_overrides[get_publisher] = lambda: publisher
    yield publisher
    app.dependency_overrides.pop(get_publisher, None)


@pytest_asyncio.fixture
async def client(session_factory, scan_queue, event_publisher):
    async def _get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_task_enqueuer] = lambda: scan_queue
    app.state.audit_session_factory = session_factory

    async with session_factory() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password("admin1234"), role="admin"),
                User(
                    username="analyst",
                    password_hash=hash_password("analyst1234"),
                    role="analyst",
                ),
            ]
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    app.state.audit_session_factory = None


async def login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
