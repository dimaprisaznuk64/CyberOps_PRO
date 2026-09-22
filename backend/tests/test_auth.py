from __future__ import annotations

from tests.conftest import login


async def test_register_and_me(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "password": "password123", "role": "user"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "user"

    token = await login(client, "alice", "password123")
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


async def test_register_duplicate_username(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "bob", "password": "password123"}
    )
    resp = await client.post(
        "/api/v1/auth/register", json={"username": "bob", "password": "password123"}
    )
    assert resp.status_code == 409


async def test_register_short_password(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"username": "carl", "password": "123"}
    )
    assert resp.status_code == 422


async def test_login_wrong_password(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "dave", "password": "password123"}
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "dave", "password": "wrongpass1"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_change_password(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "erin", "password": "password123"}
    )
    token = await login(client, "erin", "password123")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "password123", "new_password": "newpassword123"},
        headers=headers,
    )
    assert resp.status_code == 204

    resp = await client.post(
        "/api/v1/auth/login", json={"username": "erin", "password": "newpassword123"}
    )
    assert resp.status_code == 200
