"""Архів сирого nmap-XML: ендпоинти /raw і /raw.xml."""

from __future__ import annotations

import gzip

from app.main import app as core_app
from app.models.scan import Scan
from app.services.raw_nmap import pack_raw_xml
from sqlalchemy import update

from services.scanner.nmap_runner import parse_nmap_xml
from tests.conftest import login
from tests.test_nmap_runner import DEEP_XML


async def _create_asset(client, token: str) -> int:
    resp = await client.post(
        "/api/v1/assets",
        json={"name": "web", "host": "127.0.0.1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _new_scan(client, token: str) -> int:
    """Скан у статусі pending — архіву ще немає (воркер у тестах не крутиться)."""
    headers = {"Authorization": f"Bearer {token}"}
    asset_id = await _create_asset(client, token)
    resp = await client.post("/api/v1/scans", json={"asset_id": asset_id}, headers=headers)
    assert resp.status_code == 202, resp.text
    return resp.json()["id"]


async def _store_archive(scan_id: int, xml: str, *, gz: bool = True) -> None:
    """Кладе архів у scans так, як це робить воркер після nmap."""
    packed, _size, _sha = pack_raw_xml(xml)
    async with core_app.state.audit_session_factory() as session:
        await session.execute(
            update(Scan)
            .where(Scan.id == scan_id)
            .values(
                status="done",
                raw_xml_gz=packed if gz else None,
                raw_xml=None if gz else xml,
                result=parse_nmap_xml(xml),
                risk_score=12,
                risk_level="LOW",
            )
        )
        await session.commit()


async def test_raw_metadata_and_xml(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML)

    resp = await client.get(f"/api/v1/scans/{scan_id}/raw", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is True
    assert body["compressed"] is True
    assert body["hosts_count"] == 1
    assert body["nmap_version"] == "7.95"
    assert body["nmap_args"] == "nmap -sT -sV -oX - 10.0.0.5"
    assert body["size_bytes"] == len(DEEP_XML.encode("utf-8"))
    assert len(body["sha256"]) == 64
    assert body["truncated"] is False
    assert body["xml"] == DEEP_XML
    # «deep»-шари доїжджають до клієнта разом з метаданими
    assert body["parsed"]["stats"]["hosts_total"] == 3
    assert body["parsed"]["hosts"][0]["os_matches"][0]["name"] == "Linux 5.X"


async def test_raw_xml_stays_out_of_scan_detail(client):
    """Сторінка сканування не тягне сирий XML — він в окремому ендпоинті."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML)

    body = (await client.get(f"/api/v1/scans/{scan_id}", headers=headers)).json()
    assert "raw_xml" not in body
    assert "raw_xml_gz" not in body


async def test_raw_without_xml_body(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML)

    body = (
        await client.get(f"/api/v1/scans/{scan_id}/raw?include_xml=false", headers=headers)
    ).json()
    assert body["xml"] is None
    assert body["available"] is True
    assert body["sha256"]


async def test_raw_truncates_big_xml(client, monkeypatch):
    """Великий XML не вкладається в JSON — лишаються метадані і прапор."""
    monkeypatch.setattr("app.routers.scans.settings.scan_raw_xml_max_chars", 100)
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML)

    body = (await client.get(f"/api/v1/scans/{scan_id}/raw", headers=headers)).json()
    assert body["truncated"] is True
    assert body["xml"] is None
    assert body["size_bytes"] > 100


async def test_download_returns_attachment(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML)

    resp = await client.get(f"/api/v1/scans/{scan_id}/raw.xml", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/xml")
    assert 'filename="nmap-10.0.0.5-' in resp.headers["content-disposition"]
    assert resp.content.decode("utf-8") == DEEP_XML


async def test_download_reads_legacy_plain_column(client):
    """Скани до міграції 0007 лежать у raw_xml (Text) — архів мусить їх читати."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML, gz=False)

    body = (await client.get(f"/api/v1/scans/{scan_id}/raw", headers=headers)).json()
    assert body["xml"] == DEEP_XML
    assert body["compressed"] is False

    resp = await client.get(f"/api/v1/scans/{scan_id}/raw.xml", headers=headers)
    assert resp.status_code == 200
    assert resp.content.decode("utf-8") == DEEP_XML


async def test_broken_archive_does_not_hide_the_scan(client):
    """Битий gzip -> 500 на архіві, але сам скан лишається доступним."""
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)
    await _store_archive(scan_id, DEEP_XML)

    async with core_app.state.audit_session_factory() as session:
        await session.execute(
            update(Scan).where(Scan.id == scan_id).values(raw_xml_gz=b"not a gzip stream")
        )
        await session.commit()

    resp = await client.get(f"/api/v1/scans/{scan_id}/raw", headers=headers)
    assert resp.status_code == 500
    assert "розпакувати" in resp.json()["detail"]

    assert (await client.get(f"/api/v1/scans/{scan_id}", headers=headers)).status_code == 200


async def test_raw_absent_for_pending_scan(client):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    scan_id = await _new_scan(client, token)

    body = (await client.get(f"/api/v1/scans/{scan_id}/raw", headers=headers)).json()
    assert body["available"] is False
    assert body["xml"] is None
    assert body["size_bytes"] == 0
    assert body["parsed"] is None

    assert (
        await client.get(f"/api/v1/scans/{scan_id}/raw.xml", headers=headers)
    ).status_code == 404


async def test_raw_hidden_from_other_users(client):
    await client.post(
        "/api/v1/auth/register", json={"username": "viewer", "password": "password123"}
    )
    analyst = await login(client, "analyst", "analyst1234")
    scan_id = await _new_scan(client, analyst)
    await _store_archive(scan_id, DEEP_XML)

    viewer = await login(client, "viewer", "password123")
    headers = {"Authorization": f"Bearer {viewer}"}
    assert (
        await client.get(f"/api/v1/scans/{scan_id}/raw", headers=headers)
    ).status_code == 404
    assert (
        await client.get(f"/api/v1/scans/{scan_id}/raw.xml", headers=headers)
    ).status_code == 404


async def test_raw_requires_auth(client):
    assert (await client.get("/api/v1/scans/1/raw")).status_code == 401
    assert (await client.get("/api/v1/scans/1/raw.xml")).status_code == 401


def test_pack_is_deterministic_and_smaller():
    """Однаковий XML -> однакові байти; gzip має реально стискати."""
    packed_a, size_a, sha = pack_raw_xml(DEEP_XML)
    packed_b, size_b, sha_b = pack_raw_xml(DEEP_XML)
    assert packed_a == packed_b
    assert size_a == size_b == len(DEEP_XML.encode("utf-8"))
    assert sha == sha_b
    assert gzip.decompress(packed_a).decode("utf-8") == DEEP_XML
    assert len(packed_a) < size_a
