from __future__ import annotations

from app.models.notification import Notification
from app.models.scan import SCAN_DONE, Scan
from tests.conftest import login


async def _analyst_id(session_factory) -> int:
    from sqlalchemy import select

    from app.models.user import User

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "analyst"))
        assert user is not None
        return user.id


async def test_dashboard_stats(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/dashboard", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["unread_notifications"] == 0
    assert body["total_assets"] == 0
    assert body["recent_scans"] == []

    asset_resp = await client.post(
        "/api/v1/assets",
        json={"name": "web", "host": "127.0.0.1"},
        headers=headers,
    )
    asset_id = asset_resp.json()["id"]
    analyst_id = await _analyst_id(session_factory)

    async with session_factory() as session:
        scan = Scan(
            asset_id=asset_id,
            created_by=analyst_id,
            status=SCAN_DONE,
            risk_score=50,
            risk_level="HIGH",
        )
        session.add(scan)
        await session.commit()
        scan_id = scan.id
        session.add(
            Notification(user_id=analyst_id, title="t", body="b", is_read=False)
        )
        await session.commit()

    resp = await client.get("/api/v1/dashboard", headers=headers)
    body = resp.json()
    assert body["unread_notifications"] == 1
    assert body["total_assets"] == 1
    assert body["high_risk_scans"] == 1
    assert [s["id"] for s in body["recent_scans"]] == [scan_id]
    assert body["recent_scans"][0]["risk_level"] == "HIGH"


async def test_dashboard_scoped_to_user(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(
        "/api/v1/assets",
        json={"name": "web", "host": "127.0.0.1"},
        headers=headers,
    )

    data = (await client.get("/api/v1/dashboard", headers=headers)).json()
    assert data["total_assets"] == 1

    await client.post(
        "/api/v1/auth/register", json={"username": "viewer5", "password": "password123"}
    )
    user_token = await login(client, "viewer5", "password123")
    user_data = (
        await client.get(
            "/api/v1/dashboard", headers={"Authorization": f"Bearer {user_token}"}
        )
    ).json()
    assert user_data["total_assets"] == 0
    assert user_data["recent_scans"] == []

async def test_legacy_dashboard_page_is_served(client):
    """Стара сторінка лишилась доступною на /dashboard — вона потрібна для
    зворотної сумісності (окремий CSP для неї заданий у gateway)."""
    # без слеша mount віддає 307 на /dashboard/ — це нормальна поведінка StaticFiles
    resp = await client.get("/dashboard/")
    assert resp.status_code == 200, resp.text
    assert "text/html" in resp.headers["content-type"]
    assert "CyberOps Dashboard" in resp.text


async def test_legacy_dashboard_does_not_expose_frontend_dir(client):
    """Раніше на /dashboard монтувався весь frontend/, а gateway не вимагає
    токен для цього шляху — тож публічно віддавалися node_modules,
    .env.example, next.config.mjs. Тепер має віддаватися тільки сторінка."""
    for path in (
        "/dashboard/package.json",
        "/dashboard/.env.example",
        "/dashboard/next.config.mjs",
        "/dashboard/next-env.d.ts",
        "/dashboard/src",
    ):
        resp = await client.get(path)
        assert resp.status_code == 404, f"{path} -> {resp.status_code}"
