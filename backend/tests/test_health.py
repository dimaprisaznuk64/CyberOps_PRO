from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as c:
        resp = c.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
