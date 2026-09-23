from __future__ import annotations

from app.models.finding import Finding
from app.models.scan import SCAN_DONE, Scan
from app.models.service import Service
from app.models.user import User
from sqlalchemy import select

from tests.conftest import login


async def _user_id(session_factory, username: str) -> int:
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == username))
        assert user is not None
        return user.id


async def _seed_completed_scan(session_factory, owner_id: int, asset_id: int) -> int:
    async with session_factory() as session:
        scan = Scan(
            asset_id=asset_id,
            created_by=owner_id,
            status=SCAN_DONE,
            risk_score=40,
            risk_level="MEDIUM",
        )
        session.add(scan)
        await session.flush()
        svc = Service(
            scan_id=scan.id,
            host="127.0.0.1",
            port=23,
            protocol="tcp",
            state="open",
            service="telnet",
            product="",
            version="",
            cpe="",
        )
        session.add(svc)
        await session.flush()
        session.add(
            Finding(
                scan_id=scan.id,
                service_id=svc.id,
                severity="high",
                title="Telnet відкритий",
                description="desc",
                recommendation="rec",
            )
        )
        await session.commit()
        return scan.id


async def _create_asset(client, token: str) -> int:
    resp = await client.post(
        "/api/v1/assets",
        json={"name": "web", "host": "127.0.0.1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_scan_services_and_risk(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id(session_factory, "analyst")
    asset_id = await _create_asset(client, token)
    scan_id = await _seed_completed_scan(session_factory, owner_id, asset_id)

    resp = await client.get(f"/api/v1/scans/{scan_id}/services", headers=headers)
    assert resp.status_code == 200, resp.text
    services = resp.json()
    assert len(services) == 1
    assert services[0]["port"] == 23
    assert services[0]["service"] == "telnet"

    resp = await client.get(f"/api/v1/scans/{scan_id}/risk", headers=headers)
    assert resp.status_code == 200, resp.text
    risk = resp.json()
    assert risk["risk_score"] == 40
    assert risk["risk_level"] == "MEDIUM"
    assert risk["services_count"] == 1
    assert risk["findings_by_severity"] == {"high": 1}


async def test_findings_list_and_filters(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id(session_factory, "analyst")
    asset_id = await _create_asset(client, token)
    scan_id = await _seed_completed_scan(session_factory, owner_id, asset_id)

    resp = await client.get("/api/v1/findings", headers=headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1
    assert resp.json()[0]["severity"] == "high"

    resp = await client.get(f"/api/v1/findings?scan_id={scan_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get("/api/v1/findings?severity=medium", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get("/api/v1/findings?severity=evil", headers=headers)
    assert resp.status_code == 422


async def test_user_sees_only_own_scan_data(client, session_factory):
    analyst_token = await login(client, "analyst", "analyst1234")
    analyst_id = await _user_id(session_factory, "analyst")
    asset_id = await _create_asset(client, analyst_token)
    scan_id = await _seed_completed_scan(session_factory, analyst_id, asset_id)

    await client.post(
        "/api/v1/auth/register", json={"username": "viewer2", "password": "password123"}
    )
    user_token = await login(client, "viewer2", "password123")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    resp = await client.get(f"/api/v1/scans/{scan_id}/risk", headers=user_headers)
    assert resp.status_code == 404

    resp = await client.get("/api/v1/findings", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == []