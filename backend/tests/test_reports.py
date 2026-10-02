from __future__ import annotations

from app.models.finding import Finding
from app.models.scan import SCAN_DONE, Scan
from app.models.service import Service
from tests.conftest import login


async def _analyst_id(session_factory) -> int:
    from sqlalchemy import select

    from app.models.user import User

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "analyst"))
        assert user is not None
        return user.id


async def _seed_asset_and_scan(client, token: str, session_factory) -> tuple[int, int]:
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/v1/assets",
        json={"name": "web", "host": "127.0.0.1"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    asset_id = resp.json()["id"]
    owner_id = await _analyst_id(session_factory)

    async with session_factory() as session:
        scan = Scan(
            asset_id=asset_id,
            created_by=owner_id,
            status=SCAN_DONE,
            risk_score=25,
            risk_level="MEDIUM",
        )
        session.add(scan)
        await session.flush()
        service = Service(
            scan_id=scan.id,
            host="127.0.0.1",
            port=22,
            protocol="tcp",
            state="open",
            service="ssh",
            product="OpenSSH",
            version="9.0",
            cpe="",
        )
        session.add(service)
        await session.flush()
        session.add(
            Finding(
                scan_id=scan.id,
                service_id=service.id,
                severity="low",
                title="SSH відкритий",
                description="desc",
                recommendation="rec",
            )
        )
        await session.commit()
        return asset_id, scan.id


async def test_analyst_creates_asset_report(client, session_factory, event_publisher):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    asset_id, _ = await _seed_asset_and_scan(client, token, session_factory)

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Звіт по активу", "report_type": "asset", "asset_id": asset_id},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["report_type"] == "asset"
    assert body["content"]["asset"]["host"] == "127.0.0.1"
    assert body["content"]["summary"]["total_scans"] == 1
    assert body["content"]["summary"]["findings_by_severity"] == {"low": 1}
    assert len(body["content"]["scans"]) == 1
    assert body["content"]["scans"][0]["services"][0]["service"] == "ssh"

    generated = [
        payload
        for event_type, payload in event_publisher.events
        if event_type == "report.generated"
    ]
    assert len(generated) == 1
    assert generated[0]["report_type"] == "asset"


async def test_analyst_creates_scan_report(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    _, scan_id = await _seed_asset_and_scan(client, token, session_factory)

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Звіт по скану", "report_type": "scan", "scan_id": scan_id},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["content"]["summary"]["total_scans"] == 1


async def test_reports_validation(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "x", "report_type": "bad"},
        headers=headers,
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "x", "report_type": "asset"},
        headers=headers,
    )
    assert resp.status_code == 422

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "x", "report_type": "scan", "scan_id": 9999},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_report_on_missing_target_is_404(client):
    """Звіт за неіснуючим об'єктом — 404, а не 500 і не порожній звіт."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "x", "report_type": "asset", "asset_id": 999999},
        headers=headers,
    )
    assert resp.status_code == 404

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "x", "report_type": "scan", "scan_id": 999999},
        headers=headers,
    )
    assert resp.status_code == 404


async def _promote_to_analyst(client, username: str) -> None:
    admin_token = await login(client, "admin", "admin1234")
    users = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    target = next(u for u in users.json() if u["username"] == username)
    await client.patch(
        f"/api/v1/users/{target['id']}/role",
        json={"role": "analyst"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


async def test_analyst_cannot_report_on_others_asset(client, session_factory):
    """Актив бачить лише власник або admin — і звіт по ньому теж.

    Правило беремо з assets.py:47, тож модель ролей послідовна: аналітик не
    бачить чужого актива і не може зібрати по ньому звіт, навіть знаючи ID.
    """
    owner_token = await login(client, "analyst", "analyst1234")
    asset_id, _ = await _seed_asset_and_scan(client, owner_token, session_factory)

    await client.post(
        "/api/v1/auth/register", json={"username": "second_analyst", "password": "password123"}
    )
    await _promote_to_analyst(client, "second_analyst")
    other_token = await login(client, "second_analyst", "password123")

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Чужий актив", "report_type": "asset", "asset_id": asset_id},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


async def test_analyst_can_report_on_others_scan(client, session_factory):
    """Сканування аналітик бачить усі — і звіт по чужому скану теж.

    Правило беремо з scans.py:52-53. Тест фіксує це рішення: якщо модель
    колись змінять на «аналітик — тільки свої», тест впаде і про це доведеться
    подумати свідомо.
    """
    owner_token = await login(client, "analyst", "analyst1234")
    _, scan_id = await _seed_asset_and_scan(client, owner_token, session_factory)

    await client.post(
        "/api/v1/auth/register", json={"username": "third_analyst", "password": "password123"}
    )
    await _promote_to_analyst(client, "third_analyst")
    other_token = await login(client, "third_analyst", "password123")

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Чужий скан", "report_type": "scan", "scan_id": scan_id},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["content"]["summary"]["total_scans"] == 1


async def test_reports_list_and_access(client, session_factory):
    analyst_token = await login(client, "analyst", "analyst1234")
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
    asset_id, _ = await _seed_asset_and_scan(client, analyst_token, session_factory)

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Звіт", "report_type": "asset", "asset_id": asset_id},
        headers=analyst_headers,
    )
    report_id = resp.json()["id"]

    resp = await client.get("/api/v1/reports", headers=analyst_headers)
    assert resp.status_code == 200
    assert any(r["id"] == report_id for r in resp.json())

    resp = await client.get(f"/api/v1/reports/{report_id}", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Звіт"

    await client.post(
        "/api/v1/auth/register", json={"username": "viewer4", "password": "password123"}
    )
    user_token = await login(client, "viewer4", "password123")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    resp = await client.get(f"/api/v1/reports/{report_id}", headers=user_headers)
    assert resp.status_code == 404

    resp = await client.post(
        "/api/v1/reports",
        json={"title": "x", "report_type": "asset", "asset_id": asset_id},
        headers=user_headers,
    )
    assert resp.status_code == 403