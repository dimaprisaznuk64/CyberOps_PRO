from __future__ import annotations

from tests.conftest import login


async def _create_target(client, token: str) -> int:
    resp = await client.post(
        "/api/v1/targets",
        json={"name": "web", "host": "127.0.0.1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_role_user_cannot_scan(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    token = await login(client, "viewer", "password123")
    resp = await client.post(
        "/api/v1/scans",
        json={"target_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_analyst_creates_scan_and_enqueues(client, scan_queue):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    target_id = await _create_target(client, token)

    resp = await client.post(
        "/api/v1/scans",
        json={"target_id": target_id, "scan_type": "quick", "ports": "22,80"},
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["scan_type"] == "quick"

    assert len(scan_queue.calls) == 1
    scan_id, host, scan_type, ports = scan_queue.calls[0]
    assert scan_id == body["id"]
    assert host == "127.0.0.1"
    assert scan_type == "quick"
    assert ports == "22,80"


async def test_invalid_scan_type_rejected(client):
    token = await login(client, "analyst", "analyst1234")
    target_id = await _create_target(client, token)
    resp = await client.post(
        "/api/v1/scans",
        json={"target_id": target_id, "scan_type": "evil"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_missing_target_rejected(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/scans",
        json={"target_id": 999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_get_scan_result(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    target_id = await _create_target(client, token)
    resp = await client.post(
        "/api/v1/scans", json={"target_id": target_id}, headers=headers
    )
    scan_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/scans/{scan_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == scan_id
    assert resp.json()["result"] is None
