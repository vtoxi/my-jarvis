from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_sibling_paths() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/sibling-projects/paths")
        assert res.status_code == 200
        body = res.json()
        assert "open_interpreter_dir" in body
        assert "crewai_dir" in body
        assert "open-interpreter" in body["open_interpreter_dir"] or body["open_interpreter_dir"]


def test_sibling_status() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/sibling-projects/status")
        assert res.status_code == 200
        body = res.json()
        assert body["open_interpreter"]["running"] is False
        assert body["crewai"]["running"] is False


def test_sibling_start_blocked_in_sandbox() -> None:
    prev = settings.automation_sandbox
    settings.automation_sandbox = True
    try:
        with TestClient(create_app()) as client:
            res = client.post("/sibling-projects/open-interpreter/start", json={})
            assert res.status_code == 200
            assert res.json().get("ok") is False
            assert res.json().get("reason") == "automation_sandbox"
    finally:
        settings.automation_sandbox = prev
