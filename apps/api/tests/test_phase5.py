from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_copilot_status_ok() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/copilot/status")
        assert res.status_code == 200
        body = res.json()
        assert "monitoring_paused" in body
        assert "assist_mode" in body


def test_screen_context_ok() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/screen/context")
        assert res.status_code == 200
        body = res.json()
        assert body.get("visible_indicator") is True


def test_focus_state_and_control() -> None:
    with TestClient(create_app()) as client:
        r0 = client.get("/focus/state")
        assert r0.json()["running"] is False
        r1 = client.post("/focus/control", json={"action": "start"})
        assert r1.status_code == 200
        r2 = client.get("/focus/state")
        assert r2.json()["running"] is True
        r3 = client.post("/focus/control", json={"action": "stop"})
        assert r3.status_code == 200
        assert client.get("/focus/state").json()["running"] is False


def test_capture_respects_pause() -> None:
    with TestClient(create_app()) as client:
        client.post("/copilot/config", json={"monitoring_paused": True})
        res = client.post("/screen/capture", json={"include_image": False})
        assert res.status_code == 200
        body = res.json()
        assert body.get("ok") is False
        assert body.get("reason") == "monitoring_paused"
        client.post("/copilot/config", json={"monitoring_paused": False})
