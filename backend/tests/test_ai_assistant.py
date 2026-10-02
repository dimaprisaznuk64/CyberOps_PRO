from __future__ import annotations

from sqlalchemy import select

from app.models.finding import Finding
from tests.conftest import login
from tests.test_findings import _create_asset, _seed_completed_scan, _user_id


async def _first_finding_id(session_factory, scan_id: int) -> int:
    async with session_factory() as session:
        finding = await session.scalar(select(Finding).where(Finding.scan_id == scan_id))
        assert finding is not None
        return finding.id


async def test_explain_finding_rule_based(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    headers = {"Authorization": f"Bearer {token}"}
    owner_id = await _user_id(session_factory, "analyst")
    asset_id = await _create_asset(client, token)
    scan_id = await _seed_completed_scan(session_factory, owner_id, asset_id)
    finding_id = await _first_finding_id(session_factory, scan_id)

    resp = await client.post(
        f"/api/v1/findings/{finding_id}/explain", headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider"] == "rule"
    assert body["explanation"]
    assert "Telnet" in body["explanation"]
    assert body["impact"]
    assert "7" in body["risk_explanation"]
    assert body["remediation"]


async def test_explain_finding_access_denied(client, session_factory):
    token = await login(client, "analyst", "analyst1234")
    owner_id = await _user_id(session_factory, "analyst")
    asset_id = await _create_asset(client, token)
    scan_id = await _seed_completed_scan(session_factory, owner_id, asset_id)
    finding_id = await _first_finding_id(session_factory, scan_id)

    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": "user_x", "password": "user1234", "role": "user"},
    )
    assert resp.status_code == 201, resp.text
    user_token = await login(client, "user_x", "user1234")

    resp = await client.post(
        f"/api/v1/findings/{finding_id}/explain",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


async def test_explain_finding_llm_fallback(monkeypatch):
    from app.services import ai_assistant

    async def _post(url, headers, json):
        raise RuntimeError("llm connection refused")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        post = _post

    monkeypatch.setattr(ai_assistant.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(ai_assistant.settings, "ai_provider", "ollama")

    finding = Finding(title="SSH зі слабким шифром", severity="high", recommendation="rec")
    result = await ai_assistant.explain_finding(finding)

    assert result.provider == "rule"
    assert result.explanation
    assert "7" in result.risk_explanation
    assert result.remediation == "rec"