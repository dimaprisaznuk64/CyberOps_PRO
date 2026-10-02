from __future__ import annotations

from app.models.notification import Notification
from tests.conftest import login


async def _seed_notification(session_factory, user_id: int) -> int:
    async with session_factory() as session:
        notification = Notification(
            user_id=user_id, title="Сканування завершено", body="127.0.0.1", is_read=False
        )
        session.add(notification)
        await session.commit()
        return notification.id


async def _analyst_id(session_factory) -> int:
    from sqlalchemy import select

    from app.models.user import User

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "analyst"))
        assert user is not None
        return user.id


async def test_user_sees_only_own_notifications(client, session_factory):
    analyst_token = await login(client, "analyst", "analyst1234")
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
    analyst_id = await _analyst_id(session_factory)
    notification_id = await _seed_notification(session_factory, analyst_id)

    await client.post(
        "/api/v1/auth/register", json={"username": "viewer3", "password": "password123"}
    )
    user_token = await login(client, "viewer3", "password123")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    resp = await client.get("/api/v1/notifications", headers=analyst_headers)
    assert resp.status_code == 200
    assert any(n["id"] == notification_id for n in resp.json())

    resp = await client.get("/api/v1/notifications", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(f"/api/v1/notifications/{notification_id}", headers=user_headers)
    assert resp.status_code == 404


async def test_mark_read_and_read_all(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    analyst_id = await _analyst_id(session_factory)

    first = await _seed_notification(session_factory, analyst_id)
    second = await _seed_notification(session_factory, analyst_id)

    resp = await client.patch(
        f"/api/v1/notifications/{first}/read",
        json={"is_read": True},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_read"] is True

    resp = await client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()]
    assert first not in ids
    assert second in ids

    resp = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == 1

    resp = await client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert resp.json() == []