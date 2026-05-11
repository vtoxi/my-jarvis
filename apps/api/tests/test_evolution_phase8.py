from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app
from app.services.evolution_approval import mint_learn_approval_token, verify_learn_approval_token


def test_evolution_status_ok(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        res = client.get("/evolution/status")
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body.get("twin_version"), int) and body.get("twin_version") >= 1
        assert "strategic_maturity_index" in body
        assert body.get("idle_schedule_enabled") is False
        assert body.get("idle_schedule_interval_s") is None
        assert "knowledge_chunk_count" in body
        assert body.get("knowledge_enabled") is True


def test_evolution_status_reflects_idle_schedule_flags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    monkeypatch.setattr(settings, "evolution_idle_enabled", True)
    monkeypatch.setattr(settings, "evolution_idle_schedule_enabled", True)
    monkeypatch.setattr(settings, "evolution_idle_schedule_interval_s", 1800)
    with TestClient(create_app()) as client:
        res = client.get("/evolution/status")
        assert res.status_code == 200
        body = res.json()
        assert body.get("idle_schedule_enabled") is True
        assert body.get("idle_schedule_interval_s") == 1800


def test_evolution_twin_patch_and_rollback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        res = client.patch(
            "/evolution/twin",
            json={
                "profile": {
                    "workflow": {"morning": "slack_first"},
                    "decision": {},
                    "communication": {"brevity": "high"},
                    "focus": {},
                    "strategy": {},
                    "meta": {},
                },
                "correction_note": "test correction",
            },
        )
        assert res.status_code == 200
        assert res.json()["version"] >= 2
        rb = client.post("/evolution/rollback", json={"steps": 1})
        assert rb.status_code == 200
        assert rb.json().get("ok") is True


def test_evolution_learn_approve_roundtrip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    with TestClient(create_app()) as client:
        lr = client.post(
            "/evolution/learn",
            json={"source": "manual", "summary": "prefer morning focus", "detail": {}, "requires_approval": True},
        )
        assert lr.status_code == 200
        body = lr.json()
        assert body.get("pending_id") and body.get("approval_token")
        ap = client.post(
            "/evolution/approve",
            json={"approval_token": body["approval_token"], "pending_id": body["pending_id"]},
        )
        assert ap.status_code == 200
        assert ap.json().get("ok") is True


def test_learn_approval_token_verify() -> None:
    pid = "pending-test-uuid-0001"
    tok, _ = mint_learn_approval_token(settings, pending_id=pid)
    v = verify_learn_approval_token(settings, token=tok, pending_id=pid)
    assert v.pending_id == pid


@pytest.mark.asyncio
async def test_evolution_store_rollback_empty(tmp_path, monkeypatch) -> None:
    from app.services.evolution_store import EvolutionStore

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    store = EvolutionStore(settings)
    await store.setup()
    ok, ver, msg = await store.rollback_twin(1)
    assert ok is False
    assert ver >= 1
