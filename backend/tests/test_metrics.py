from __future__ import annotations

from app.main import app
from app.services.metrics import describe_path
from fastapi.testclient import TestClient


def test_metrics_exposes_http_requests_total():
    with TestClient(app) as c:
        resp = c.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert "http_requests_total" in resp.text


async def test_metrics_recorded_by_middleware(client):
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "x", "password": "y"}
    )
    assert resp.status_code == 401
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert 'path="/api/v1/auth"' in metrics.text
    assert 'status="401"' in metrics.text


def test_describe_path_buckets():
    assert describe_path("/api/v1/scans/42/services") == "/api/v1/scans"
    assert describe_path("/api/v1/scans/42") == "/api/v1/scans"
    assert describe_path("/api/v1/auth/login") == "/api/v1/auth"
    assert describe_path("/") == "/"