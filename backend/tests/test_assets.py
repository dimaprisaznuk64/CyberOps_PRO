from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.main import app as core_app
from app.models.scan import Scan
from tests.conftest import login


async def _make_asset(client, token: str, name: str = "web", host: str = "10.0.0.1") -> int:
    resp = await client.post(
        "/api/v1/assets",
        json={"name": name, "host": host},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _finish_scan(asset_id: int, risk_score: int, finished_at: datetime) -> int:
    """Імітує завершений скан: воркер у тестах не крутиться."""
    async with core_app.state.audit_session_factory() as session:
        scan = Scan(
            asset_id=asset_id,
            created_by=2,
            status="done",
            scan_type="quick",
            risk_score=risk_score,
            risk_level="LOW" if risk_score < 20 else "MEDIUM",
            finished_at=finished_at,
        )
        session.add(scan)
        await session.commit()
        return scan.id


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

async def test_asset_without_scans_has_no_risk(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _make_asset(client, token)

    body = (await client.get(f"/api/v1/assets/{asset_id}", headers=headers)).json()
    assert body["risk_score"] is None
    assert body["risk_level"] is None
    assert body["max_risk_score"] is None
    assert body["scans_count"] == 0
    assert body["last_scan_at"] is None


async def test_asset_risk_uses_latest_scan_and_keeps_maximum(client):
    """Поточний стан — останнє сканування, але історія не забувається."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _make_asset(client, token)

    now = datetime.now(UTC)
    await _finish_scan(asset_id, 80, now - timedelta(days=2))
    await _finish_scan(asset_id, 12, now - timedelta(hours=1))

    body = (await client.get(f"/api/v1/assets/{asset_id}", headers=headers)).json()
    assert body["risk_score"] == 12
    assert body["risk_level"] == "LOW"
    assert body["max_risk_score"] == 80
    assert body["max_risk_level"] == "CRITICAL"
    assert body["scans_count"] == 2
    assert body["last_scan_at"] is not None


async def test_latest_scan_wins_on_equal_timestamps(client):
    """Два сканування з однаковим finished_at: перемагає останнє за id.

    Повторний скан часто стартує в ту ж секунду, що й попередній (черга,
    ретрай), тож розв'язка лише за часом була б невизначеною.
    """
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _make_asset(client, token)

    moment = datetime.now(UTC)
    await _finish_scan(asset_id, 90, moment)
    await _finish_scan(asset_id, 5, moment)

    body = (await client.get(f"/api/v1/assets/{asset_id}", headers=headers)).json()
    assert body["risk_score"] == 5
    assert body["max_risk_score"] == 90
    assert body["max_risk_level"] == "CRITICAL"


async def test_failed_scan_counts_but_gives_no_risk(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _make_asset(client, token)
    now = datetime.now(UTC)
    await _finish_scan(asset_id, 30, now)
    await _finish_scan(asset_id, 30, now)  # друга «спроба» — залишимо failed
    async with core_app.state.audit_session_factory() as session:
        scan = Scan(
            asset_id=asset_id,
            created_by=2,
            status="failed",
            scan_type="tcp",
            error="nmap не знайдено",
            finished_at=now + timedelta(minutes=5),
        )
        session.add(scan)
        await session.commit()

    body = (await client.get(f"/api/v1/assets/{asset_id}", headers=headers)).json()
    assert body["scans_count"] == 3
    assert body["risk_score"] == 30  # лише завершені сканування дають ризик
    assert body["last_scan_at"] > now.isoformat().replace("+00:00", "")


async def test_asset_list_aggregates_risk(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    risky = await _make_asset(client, token, "risky", "10.0.0.1")
    clean = await _make_asset(client, token, "clean", "10.0.0.2")
    await _finish_scan(clean, 3, datetime.now(UTC))

    body = (await client.get("/api/v1/assets", headers=headers)).json()
    by_id = {item["id"]: item for item in body}
    assert by_id[risky]["risk_score"] is None
    assert by_id[clean]["risk_score"] == 3
    assert by_id[clean]["risk_level"] == "LOW"


async def test_asset_risk_not_leaked_to_other_users(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    analyst = await login(client, "analyst", "analyst1234")
    asset_id = await _make_asset(client, analyst)
    await _finish_scan(asset_id, 95, datetime.now(UTC))

    viewer = await login(client, "viewer", "password123")
    headers = {"Authorization": f"Bearer {viewer}"}
    assert (await client.get("/api/v1/assets", headers=headers)).json() == []
    assert (await client.get(f"/api/v1/assets/{asset_id}", headers=headers)).status_code == 404


async def test_patch_asset_keeps_risk(client):
    """PATCH не має обнуляти ризик — інакше бейдж зникає до перезавантаження."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _make_asset(client, token)
    await _finish_scan(asset_id, 80, datetime.now(UTC))

    body = (
        await client.patch(
            f"/api/v1/assets/{asset_id}", json={"description": "prod"}, headers=headers
        )
    ).json()
    assert body["description"] == "prod"
    assert body["risk_score"] == 80
    assert body["risk_level"] == "CRITICAL"
