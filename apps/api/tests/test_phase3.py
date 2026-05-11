from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_system_status_includes_autonomy_tier(monkeypatch) -> None:
    monkeypatch.setattr(settings, "autonomy_tier", "elevated")
    with TestClient(create_app()) as client:
        res = client.get("/system/status")
        assert res.status_code == 200
        body = res.json()
        assert body.get("autonomy_tier") == "elevated"
        assert "Elevated" in (body.get("autonomy_note") or "")


def test_permissions_check_restricted() -> None:
    with TestClient(create_app()) as client:
        res = client.post(
            "/permissions/check",
            json={"steps": [{"type": "open_url", "target": "file:///etc/passwd", "tier": "safe"}]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is False


def test_kill_disarms_workflow(tmp_path: Path) -> None:
    prev = settings.data_dir, settings.automation_sandbox
    settings.data_dir = tmp_path
    settings.automation_sandbox = True
    try:
        with TestClient(create_app()) as client:
            r = client.post("/kill")
            assert r.status_code == 200
            assert r.json()["armed"] is False
            wf = client.post(
                "/workflows/run",
                json={"profile_id": "quick", "session_id": "sess-phase3-aaaaaa"},
            )
            assert wf.status_code == 200
            assert wf.json().get("ok") is False
            errs = wf.json().get("errors") or []
            assert "automation_disarmed" in errs or "disarmed" in (wf.json().get("message") or "").lower()
    finally:
        settings.data_dir, settings.automation_sandbox = prev


def test_workflow_elevated_skips_confirm_challenge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "autonomy_tier", "elevated")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "automation_sandbox", True)
    with TestClient(create_app()) as client:
        client.post("/system/arm", json={"armed": True})
        wf = client.post(
            "/workflows/run",
            json={"profile_id": "morning", "session_id": "sess-elevated-aa"},
        )
        assert wf.status_code == 200
        data = wf.json()
        assert data.get("pending") is not True
        assert data.get("ok") is True


def test_workflow_sandbox_morning(tmp_path: Path) -> None:
    prev_dir = settings.data_dir
    prev_sand = settings.automation_sandbox
    settings.data_dir = tmp_path
    settings.automation_sandbox = True
    try:
        with TestClient(create_app()) as client:
            client.post("/system/arm", json={"armed": True})
            wf = client.post(
                "/workflows/run",
                json={"profile_id": "morning", "session_id": "sess-sandbox-aaaa"},
            )
            assert wf.status_code == 200
            data = wf.json()
            # morning has confirm step — first call pending
            assert data.get("pending") is True or data.get("ok") is True
            if data.get("pending"):
                ch = data["challenge"]
                wf2 = client.post(
                    "/workflows/run",
                    json={"profile_id": "morning", "session_id": "sess-sandbox-aaaa", "challenge": ch},
                )
                assert wf2.status_code == 200
                assert wf2.json().get("ok") is True
            else:
                assert data.get("ok") is True
    finally:
        settings.data_dir = prev_dir
        settings.automation_sandbox = prev_sand


def test_workflow_mock_hammerspoon(tmp_path: Path) -> None:
    prev_dir = settings.data_dir
    prev_sand = settings.automation_sandbox
    settings.data_dir = tmp_path
    settings.automation_sandbox = False
    try:
        with TestClient(create_app()) as client:
            client.post("/system/arm", json={"armed": True})
            client.app.state.hammerspoon.dispatch = AsyncMock(return_value={"mock": True})
            wf = client.post(
                "/workflows/run",
                json={"profile_id": "quick", "session_id": "sess-hs-mock-aa"},
            )
            assert wf.status_code == 200
            assert wf.json().get("ok") is True
    finally:
        settings.data_dir = prev_dir
        settings.automation_sandbox = prev_sand
