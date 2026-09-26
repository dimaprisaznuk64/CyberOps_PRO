from __future__ import annotations

from tests.conftest import login


async def _create_asset(client, token: str) -> int:
    resp = await client.post(
        "/api/v1/assets",
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
        json={"asset_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_analyst_creates_scan_and_enqueues(client, scan_queue):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _create_asset(client, token)

    resp = await client.post(
        "/api/v1/scans",
        json={"asset_id": asset_id, "scan_type": "quick", "ports": "22,80"},
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
    asset_id = await _create_asset(client, token)
    resp = await client.post(
        "/api/v1/scans",
        json={"asset_id": asset_id, "scan_type": "evil"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_missing_asset_rejected(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.post(
        "/api/v1/scans",
        json={"asset_id": 999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_get_scan_result(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _create_asset(client, token)
    resp = await client.post(
        "/api/v1/scans", json={"asset_id": asset_id}, headers=headers
    )
    scan_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/scans/{scan_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == scan_id
    assert resp.json()["result"] is None

async def test_broker_down_does_not_leave_pending_scan(client, monkeypatch):
    """Брокер недоступний -> 503 і скан одразу failed, а не назавжди pending."""
    from app.main import app as core_app
    from app.tasks import get_task_enqueuer

    def _boom(*_args, **_kwargs):
        raise OSError("broker down")

    # ключ override — той самий об'єкт, що підставленийDepends при імпорті
    core_app.dependency_overrides[get_task_enqueuer] = lambda: _boom

    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _create_asset(client, token)

    resp = await client.post(
        "/api/v1/scans",
        json={"asset_id": asset_id},
        headers=headers,
    )
    assert resp.status_code == 503, resp.text

    scans = await client.get("/api/v1/scans", headers=headers)
    assert scans.status_code == 200
    body = scans.json()
    assert len(body) == 1
    assert body[0]["status"] == "failed"
    assert "чергу" in body[0]["error"]
