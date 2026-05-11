from fastapi.testclient import TestClient

from app.main import create_app


def test_health() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["service"] == "jarvis-api"
        assert "ollama" in body
        assert isinstance(body["ollama"], dict)
        assert "reachable" in body["ollama"]


def test_version() -> None:
    with TestClient(create_app()) as client:
        res = client.get("/version")
        assert res.status_code == 200
        body = res.json()
        assert body["version"] == "0.4.0"


def test_cors_preflight() -> None:
    with TestClient(create_app()) as client:
        res = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200
