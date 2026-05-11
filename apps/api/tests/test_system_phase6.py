from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.services.patch_service import prepare_patch
from app.services.system_evolution_store import SystemEvolutionStore
from app.services.system_patch_approval import mint_patch_apply_token, verify_patch_apply_token


def test_system_health_returns_score() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/system/health")
        assert res.status_code == 200
        body = res.json()
        assert "health_score" in body
        assert isinstance(body["health_score"], int)
        assert 0 <= body["health_score"] <= 100
        assert "subsystems" in body and len(body["subsystems"]) >= 3


def test_system_logs_endpoint() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/system/logs?lines=5")
        assert res.status_code == 200
        body = res.json()
        assert "lines" in body


def test_system_performance_stub(monkeypatch) -> None:
    monkeypatch.setattr(settings, "system_metrics_enabled", False)
    with TestClient(create_app()) as client:
        res = client.get("/system/performance")
        assert res.status_code == 200
        body = res.json()
        assert body.get("available") is False


def test_system_audit_stub_no_subprocess(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        res = client.post("/system/audit", json={"mode": "audit", "run_tools": False})
        assert res.status_code == 200
        body = res.json()
        assert body.get("audit_id")
        assert "debt_score" in body
        assert isinstance(body.get("operator_takeover_checklist"), list)
        assert len(body.get("operator_takeover_checklist") or []) >= 2


def test_system_repair_502_includes_operator_takeover(monkeypatch) -> None:
    def _boom(**_kwargs: object) -> None:
        raise RuntimeError("crew unavailable")

    monkeypatch.setattr("app.api.routes_system.run_self_healing_crew", _boom)
    with TestClient(create_app()) as client:
        res = client.post("/system/repair", json={"context": "test"})
        assert res.status_code == 502
        body = res.json()
        detail = body.get("detail")
        assert isinstance(detail, dict)
        assert detail.get("message")
        assert isinstance(detail.get("operator_takeover"), list)
        assert len(detail["operator_takeover"]) >= 2


def test_system_repair_stub(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        res = client.post("/system/repair", json={"context": "unit test"})
        assert res.status_code == 200
        body = res.json()
        assert body.get("incident_id")
        assert body.get("requires_human_approval") is True
        assert isinstance(body.get("operator_takeover_checklist"), list)
        assert len(body.get("operator_takeover_checklist") or []) >= 2


def test_patch_token_roundtrip() -> None:
    diff = "diff --git a/README.md b/README.md\n"
    pid = "00000000-0000-4000-8000-000000000001"
    branch = "jarvis-evolve-test"
    base = "abc123" * 5 + "ab"
    tok, _exp = mint_patch_apply_token(
        settings,
        patch_id=pid,
        diff_text=diff,
        branch_name=branch,
        base_sha=base,
    )
    payload = verify_patch_apply_token(settings, token=tok, diff_text=diff)
    assert payload.patch_id == pid
    assert payload.diff_sha256 == hashlib.sha256(diff.encode()).hexdigest()


def test_prepare_patch_requires_repo_root(monkeypatch) -> None:
    monkeypatch.setattr(settings, "repo_root", None)
    with pytest.raises(ValueError, match="REPO_ROOT"):
        prepare_patch(settings, diff_text="x", branch_suffix=None)


@pytest.mark.asyncio
async def test_evolution_store_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    store = SystemEvolutionStore(settings)
    await store.setup()
    iid = await store.insert_incident(
        severity="low",
        subsystem="test",
        summary="hello",
        detail={"k": 1},
    )
    rows = await store.list_incidents(limit=10)
    assert any(r["id"] == iid for r in rows)
