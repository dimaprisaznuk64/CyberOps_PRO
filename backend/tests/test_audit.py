from __future__ import annotations

from tests.conftest import login


async def test_audit_logs_requires_admin(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.get(
        "/api/v1/audit-logs", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_audit_logs_record_requests(client, session_factory):
    analyst_token = await login(client, "analyst", "analyst1234")
    resp = await client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp.status_code == 200

    admin_token = await login(client, "admin", "admin1234")
    resp = await client.get(
        "/api/v1/audit-logs?path=/api/v1/notifications",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert any(
        row["method"] == "GET" and row["path"] == "/api/v1/notifications" for row in rows
    )
    assert any(row["user_id"] is not None for row in rows)


async def test_audit_skips_health(client):
    await client.get("/health")
    admin_token = await login(client, "admin", "admin1234")
    resp = await client.get(
        "/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    assert all(row["path"] != "/health" for row in resp.json())