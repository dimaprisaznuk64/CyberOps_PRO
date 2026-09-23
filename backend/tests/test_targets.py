from __future__ import annotations

from tests.conftest import login


async def test_create_and_list_target(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/targets",
        json={"name": "router", "host": "192.168.1.1", "description": "home router"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    target_id = resp.json()["id"]

    resp = await client.get("/api/v1/targets", headers=headers)
    assert resp.status_code == 200
    assert any(t["id"] == target_id for t in resp.json())


async def test_public_host_rejected(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/targets",
        json={"name": "google-dns", "host": "8.8.8.8"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_target_requires_auth(client):
    resp = await client.get("/api/v1/targets")
    assert resp.status_code == 401


async def test_user_sees_only_own_targets(client):
    user_token = None
    resp = await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    assert resp.status_code == 201
    user_token = await login(client, "viewer", "password123")
    analyst_token = await login(client, "analyst", "analyst1234")

    await client.post(
        "/api/v1/targets",
        json={"name": "a", "host": "10.0.0.1"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    resp = await client.get(
        "/api/v1/targets", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_update_and_delete_target(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/targets", json={"name": "tmp", "host": "10.0.0.2"}, headers=headers
    )
    target_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/targets/{target_id}", json={"name": "renamed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"

    resp = await client.delete(f"/api/v1/targets/{target_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/targets/{target_id}", headers=headers)
    assert resp.status_code == 404
