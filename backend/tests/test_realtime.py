from __future__ import annotations

import pytest
from app.main import app
from app.services.auth import create_token
from app.services.realtime import publish_event
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_ws_rejects_invalid_token():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws?token=not-a-jwt"):
                pass
        assert getattr(exc.value, "code", None) == 4401


def test_ws_receives_realtime_event():
    token = create_token(42, "access")
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={token}") as ws:
            client.portal.call(
                publish_event, 42, "scan.completed", {"scan_id": 7, "risk_level": "LOW"}
            )
            data = ws.receive_json()
            assert data["type"] == "scan.completed"
            assert data["scan_id"] == 7
            assert data["risk_level"] == "LOW"


def test_ws_event_only_reaches_owner():
    token = create_token(5, "access")
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws?token={token}") as ws:
            client.portal.call(
                publish_event, 99, "scan.completed", {"scan_id": 1, "risk_level": "LOW"}
            )
            client.portal.call(
                publish_event, 5, "scan.completed", {"scan_id": 2, "risk_level": "HIGH"}
            )
            data = ws.receive_json()
            assert data["scan_id"] == 2


def test_dashboard_static_served():
    with TestClient(app) as client:
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "WebSocket" in resp.text