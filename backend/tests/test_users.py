from __future__ import annotations

from tests.conftest import login


async def test_list_users_requires_admin(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    token = await login(client, "viewer", "password123")
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_admin_can_list_users(client):
    token = await login(client, "admin", "admin1234")
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(u["username"] == "admin" for u in resp.json())


async def test_admin_change_role(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "promoted", "password": "password123"}
    )
    admin_token = await login(client, "admin", "admin1234")

    users = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    target = next(u for u in users.json() if u["username"] == "promoted")

    resp = await client.patch(
        f"/api/v1/users/{target['id']}/role",
        json={"role": "analyst"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "analyst"


async def test_admin_delete_user(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "todelete", "password": "password123"}
    )
    admin_token = await login(client, "admin", "admin1234")
    users = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    target = next(u for u in users.json() if u["username"] == "todelete")

    resp = await client.delete(
        f"/api/v1/users/{target['id']}", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 204


async def test_invalid_role_rejected(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "hacker", "password": "password123", "role": "superuser"},
    )
    assert resp.status_code == 422
