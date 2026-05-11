from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_knowledge_ingest_search_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "evolution_knowledge_enabled", True)
    with TestClient(create_app()) as client:
        st = client.get("/evolution/status")
        assert st.status_code == 200
        assert st.json().get("knowledge_chunk_count") == 0

        ing = client.post(
            "/evolution/knowledge/ingest",
            json={"source": "test", "text": "Prefer concise technical answers for code review.", "meta": {"t": 1}},
        )
        assert ing.status_code == 200
        cid = ing.json().get("chunk_id")
        assert cid

        st2 = client.get("/evolution/knowledge/status")
        assert st2.status_code == 200
        assert st2.json().get("chunk_count") == 1

        sr = client.get("/evolution/knowledge/search", params={"q": "code review concise"})
        assert sr.status_code == 200
        hits = sr.json().get("hits") or []
        assert len(hits) >= 1
        assert hits[0].get("score") is not None


def test_knowledge_disabled_returns_403(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "evolution_knowledge_enabled", False)
    with TestClient(create_app()) as client:
        r = client.post("/evolution/knowledge/ingest", json={"source": "x", "text": "hello"})
        assert r.status_code == 403


def test_learn_index_knowledge(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_stub", True)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "evolution_knowledge_enabled", True)
    with TestClient(create_app()) as client:
        lr = client.post(
            "/evolution/learn",
            json={
                "source": "manual",
                "summary": "Morning focus block 9–12",
                "detail": {},
                "requires_approval": False,
                "index_knowledge": True,
            },
        )
        assert lr.status_code == 200
        st = client.get("/evolution/knowledge/status")
        assert st.json().get("chunk_count") == 1
