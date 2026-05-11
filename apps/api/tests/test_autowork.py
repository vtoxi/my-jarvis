from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_autowork_tick_forbidden_when_disabled() -> None:
    with TestClient(create_app()) as client:
        res = client.post("/system/autowork/tick")
        assert res.status_code == 403


def test_autowork_status_defaults() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/system/autowork/status")
        assert res.status_code == 200
        body = res.json()
        assert body.get("enabled") is False
        assert body.get("schedule_enabled") is False


def test_autowork_tick_writes_last_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "autowork_enabled", True)
    monkeypatch.setattr(settings, "repo_root", None)
    monkeypatch.setattr(settings, "system_allow_subprocess", False)
    with TestClient(create_app()) as client:
        res = client.post("/system/autowork/tick")
        assert res.status_code == 200
        body = res.json()
        assert body.get("ok") is True
        assert (tmp_path / "autowork" / "last_run.json").is_file()
