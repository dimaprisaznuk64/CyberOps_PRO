from __future__ import annotations

from tests.conftest import login


async def test_create_and_list_asset(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/assets",
        json={"name": "router", "host": "192.168.1.1", "description": "home router"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["kind"] == "ip"
    asset_id = resp.json()["id"]

    resp = await client.get("/api/v1/assets", headers=headers)
    assert resp.status_code == 200
    assert any(t["id"] == asset_id for t in resp.json())


async def test_docker_asset_skips_host_check(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/assets",
        json={"name": "lab-db", "host": "db", "kind": "docker", "docker_container": "db"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["kind"] == "docker"
    assert resp.json()["docker_container"] == "db"


async def test_public_host_rejected(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/assets",
        json={"name": "google-dns", "host": "8.8.8.8"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_asset_requires_auth(client):
    resp = await client.get("/api/v1/assets")
    assert resp.status_code == 401


async def test_user_sees_only_own_assets(client):
    resp = await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    assert resp.status_code == 201
    user_token = await login(client, "viewer", "password123")
    analyst_token = await login(client, "analyst", "analyst1234")

    await client.post(
        "/api/v1/assets",
        json={"name": "a", "host": "10.0.0.1"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    resp = await client.get(
        "/api/v1/assets", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_update_and_delete_asset(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/assets", json={"name": "tmp", "host": "10.0.0.2"}, headers=headers
    )
    asset_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/assets/{asset_id}", json={"name": "renamed"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"

    resp = await client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/assets/{asset_id}", headers=headers)
    assert resp.status_code == 404