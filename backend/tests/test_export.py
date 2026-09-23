from __future__ import annotations

from tests.conftest import login


async def test_export_bad_format(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    from tests.test_reports import _seed_asset_and_scan

    asset_id, _ = await _seed_asset_and_scan(client, token, session_factory)
    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Звіт", "report_type": "asset", "asset_id": asset_id},
        headers=headers,
    )
    report_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/reports/{report_id}/export?format=xlsx", headers=headers
    )
    assert resp.status_code == 422


async def test_export_csv(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    from tests.test_reports import _seed_asset_and_scan

    asset_id, _ = await _seed_asset_and_scan(client, token, session_factory)
    resp = await client.post(
        "/api/v1/reports",
        json={"title": "Звіт", "report_type": "asset", "asset_id": asset_id},
        headers=headers,
    )
    report_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/reports/{report_id}/export?format=csv", headers=headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Content-Disposition" in resp.headers
    body = resp.text
    assert "scan_id" in body
    assert "," in body
    assert "ssh" in body


async def test_export_html(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    from tests.test_reports import _seed_asset_and_scan

    asset_id, _ = await _seed_asset_and_scan(client, token, session_factory)
    resp = await client.post(
        "/api/v1/reports",
        json={"title": "HTML-звіт", "report_type": "asset", "asset_id": asset_id},
        headers=headers,
    )
    report_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/reports/{report_id}/export?format=html", headers=headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in resp.text
    assert "HTML-звіт" in resp.text
    assert "ssh" in resp.text


async def test_export_pdf(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    from tests.test_reports import _seed_asset_and_scan

    asset_id, _ = await _seed_asset_and_scan(client, token, session_factory)
    resp = await client.post(
        "/api/v1/reports",
        json={"title": "PDF-звіт", "report_type": "asset", "asset_id": asset_id},
        headers=headers,
    )
    report_id = resp.json()["id"]

    resp = await client.get(
        f"/api/v1/reports/{report_id}/export?format=pdf", headers=headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.content.startswith(b"%PDF")


async def test_export_requires_auth(client, session_factory):
    resp = await client.get("/api/v1/reports/1/export?format=csv")
    assert resp.status_code == 401