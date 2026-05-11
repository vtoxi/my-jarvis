from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_evolution_status_includes_ethics_and_knowledge_flags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        res = client.get("/evolution/status")
        assert res.status_code == 200
        body = res.json()
        assert "ethics_note" in body and len(str(body["ethics_note"])) > 10
        assert body.get("knowledge_enabled") is True
        assert isinstance(body.get("knowledge_chunk_count"), int)


def test_learn_without_approval_has_no_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        lr = client.post(
            "/evolution/learn",
            json={"source": "manual", "summary": "preference", "detail": {}, "requires_approval": False},
        )
        assert lr.status_code == 200
        body = lr.json()
        assert body.get("approval_token") is None
        assert body.get("pending_id") is None


def test_learn_approve_rejects_bad_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        lr = client.post(
            "/evolution/learn",
            json={"source": "manual", "summary": "x", "detail": {}, "requires_approval": True},
        )
        assert lr.status_code == 200
        pid = lr.json()["pending_id"]
        ap = client.post(
            "/evolution/approve",
            json={"approval_token": "invalid-token", "pending_id": pid},
        )
        assert ap.status_code == 400


def test_twin_version_increments_on_patch_drift_guard(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        t0 = client.get("/evolution/twin")
        v0 = t0.json()["version"]
        p1 = client.patch(
            "/evolution/twin",
            json={
                "profile": {
                    "workflow": {"a": "1"},
                    "decision": {},
                    "communication": {},
                    "focus": {},
                    "strategy": {},
                    "meta": {},
                }
            },
        )
        assert p1.json()["version"] == v0 + 1
        p2 = client.patch(
            "/evolution/twin",
            json={
                "profile": {
                    "workflow": {"a": "2"},
                    "decision": {},
                    "communication": {},
                    "focus": {},
                    "strategy": {},
                    "meta": {},
                }
            },
        )
        assert p2.json()["version"] == v0 + 2


def test_sandbox_benchmark_skipped_without_repo_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "repo_root", None)
    monkeypatch.setattr(settings, "system_allow_subprocess", False)
    with TestClient(create_app()) as client:
        r = client.post("/evolution/sandbox/benchmark")
        assert r.status_code == 200
        body = r.json()
        assert body.get("skipped") is True
        assert body.get("ok") is False
