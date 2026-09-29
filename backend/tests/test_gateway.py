from __future__ import annotations

from gateway.helpers import build_forward_headers
from tests.conftest import login


def test_forward_headers_drops_spoofed_identity_and_host():
    source = {
        "Host": "evil",
        "Authorization": "Bearer x",
        "X-User-Id": "999",
        "X-User-Role": "admin",
        "content-type": "application/json",
    }
    headers = build_forward_headers(source, None, "10.0.0.5")
    assert "X-User-Id" not in headers
    assert "X-User-Role" not in headers
    assert "Host" not in headers
    assert headers["Authorization"] == "Bearer x"
    assert headers["content-type"] == "application/json"
    assert headers["X-Forwarded-For"] == "10.0.0.5"


def test_forward_headers_injects_identity_from_claims():
    source = {"Authorization": "Bearer x"}
    identity = {"sub": "7", "role": "analyst", "username": "ivan"}
    headers = build_forward_headers(source, identity, None)
    assert headers["X-User-Id"] == "7"
    assert headers["X-User-Role"] == "analyst"
    assert headers["X-User-Username"] == "ivan"


async def test_gateway_rejects_unauthenticated_api_call(client):
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 401


async def test_gateway_unknown_path_404_when_authenticated(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.get(
        "/api/v1/does-not-exist", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


async def test_gateway_login_is_public(client):
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_gateway_routes_api_to_core(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_gateway_routes_api_to_auth(client):
    token = await login(client, "analyst", "analyst1234")
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "analyst"


async def test_gateway_health_aggregates_services(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["services"] == {"auth": "ok", "core": "ok"}


async def test_gateway_liveness_does_not_check_upstreams(client):
    """Liveness не має залежати від core/auth.

    `/health` перевіряє залежності й повертає 503, коли вони не готові — це
    правильно для readiness, але не для liveness: kubelet убив би здоровий
    проксі. Регресія з kind-E2E: gateway падав у CrashLoopBackOff, поки не
    завершилися міграції (див. livenessProbe у infrastructure/kubernetes).
    """
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checked"] == "self"
    assert "services" not in body, "liveness не має ходити в залежності"


async def test_gateway_metrics(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "gateway_requests_total" in resp.text


async def test_gateway_proxies_dashboard_static(client):
    resp = await client.get("/dashboard/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "WebSocket" in resp.text