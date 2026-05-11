from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_command_stub_persists_memory(tmp_path: Path) -> None:
    prev_stub = settings.llm_stub
    prev_dir = settings.data_dir
    settings.llm_stub = True
    settings.data_dir = tmp_path
    try:
        with TestClient(create_app()) as client:
            sid = "test-session-aaaaaaaa"
            res = client.post(
                "/command",
                json={"message": "Jarvis, plan my workday", "session_id": sid, "model": "llama3"},
            )
            assert res.status_code == 200
            body = res.json()
            assert body["session_id"] == sid
            assert "reply" in body
            assert body["model"] == "llama3"
            assert len(body["agents_used"]) >= 1

            mem = client.get("/memory", params={"session_id": sid})
            assert mem.status_code == 200
            msgs = mem.json()["messages"]
            roles = [m["role"] for m in msgs]
            assert "user" in roles
            assert "assistant" in roles
    finally:
        settings.llm_stub = prev_stub
        settings.data_dir = prev_dir


def test_agents_status() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/agents/status")
        assert res.status_code == 200
        agents = res.json()["agents"]
        ids = {a["id"] for a in agents}
        assert {
            "commander",
            "planner",
            "slack",
            "interpreter",
            "executor",
            "self_healing",
            "code_audit",
            "twin_analyst",
            "idle_learning",
            "evolution_governor",
        }.issubset(ids)
