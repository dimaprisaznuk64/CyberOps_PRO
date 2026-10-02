"""Воркер кладе архів Nmap-XML у scans — саме цю ділянку не покривали тести.

Симптом живого стенду: `raw_xml_gz=packed[0]` брав перший байт gzip (0x1f =
31) замість самих стиснутих даних, тому запис падав із «a bytes-like object
is required, not 'int'». Скан не доходив до `done` і лишався `running` до
reaper'а, тобто в усякому реальному запуску сканування ламалося.

Тести архіву (`test_scan_raw_archive.py`) пишуть архів у БД руками, саме
цей запис не виконуючи — тому баг і жившов у CI.
"""

from __future__ import annotations

import gzip

from sqlalchemy import select
from workers import tasks as worker_tasks

from app.main import app as core_app
from app.models.scan import SCAN_DONE, Scan
from tests.conftest import login
from tests.test_nmap_runner import DEEP_XML


async def _new_scan(client, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    asset = await client.post(
        "/api/v1/assets",
        json={"name": "web", "host": "127.0.0.1"},
        headers=headers,
    )
    assert asset.status_code == 201, asset.text
    scan = await client.post(
        "/api/v1/scans", json={"asset_id": asset.json()["id"]}, headers=headers
    )
    assert scan.status_code == 202, scan.text
    return scan.json()["id"]


async def test_worker_stores_raw_archive_as_bytes(client, worker_env):
    token = await login(client, "analyst", "analyst1234")
    scan_id = await _new_scan(client, token)

    result = await worker_tasks._run_scan(scan_id, "127.0.0.1", "tcp", None)
    assert result["status"] == SCAN_DONE

    async with core_app.state.audit_session_factory() as session:
        scan = await session.get(Scan, scan_id)
        assert isinstance(scan.raw_xml_gz, (bytes, bytearray)), (
            f"архів має бути bytes, а не {type(scan.raw_xml_gz).__name__}"
        )
        assert gzip.decompress(scan.raw_xml_gz).decode("utf-8") == DEEP_XML
        assert scan.raw_xml is None
        assert scan.finished_at is not None
        assert scan.risk_score is not None


async def test_archive_endpoint_serves_worker_output(client, worker_env):
    """Кінець-кінцем: те, що вортер поклав, має віддаватися через /raw."""
    token = await login(client, "analyst", "analyst1234")
    scan_id = await _new_scan(client, token)
    await worker_tasks._run_scan(scan_id, "127.0.0.1", "tcp", None)

    resp = await client.get(
        f"/api/v1/scans/{scan_id}/raw",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is True
    assert body["size_bytes"] == len(DEEP_XML.encode())
    assert body["compressed"] is True
    assert body["truncated"] is False
    assert body["xml"] == DEEP_XML

    dl = await client.get(
        f"/api/v1/scans/{scan_id}/raw.xml",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dl.status_code == 200
    assert dl.text == DEEP_XML


async def test_scan_lands_in_done_and_services_are_saved(client, worker_env):
    """Статус done + сервіси/знахідки: регресія не мала б ламати й решта."""
    token = await login(client, "analyst", "analyst1234")
    scan_id = await _new_scan(client, token)
    await worker_tasks._run_scan(scan_id, "127.0.0.1", "tcp", None)

    resp = await client.get(
        f"/api/v1/scans/{scan_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == SCAN_DONE
    assert body["risk_score"] is not None
    assert "raw_xml" not in body

    async with core_app.state.audit_session_factory() as session:
        services = await session.execute(
            select(Scan).where(Scan.id == scan_id)
        )
        assert services.scalar_one().status == SCAN_DONE
