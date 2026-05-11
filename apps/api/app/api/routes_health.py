from fastapi import APIRouter, Request

from app.core.version import API_VERSION, SERVICE_NAME
from app.schemas.health import HealthResponse, OllamaHealth, VersionResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    ollama = getattr(request.app.state, "ollama", None)
    if ollama is None:
        return HealthResponse(
            status="ok",
            service=SERVICE_NAME,
            ollama=OllamaHealth(reachable=False, error="server_state_missing"),
        )
    try:
        await ollama.ping()
        ollama_health = OllamaHealth(reachable=True)
    except Exception as exc:  # noqa: BLE001
        ollama_health = OllamaHealth(reachable=False, error=str(exc))
    return HealthResponse(status="ok", service=SERVICE_NAME, ollama=ollama_health)


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    return VersionResponse(version=API_VERSION, service=SERVICE_NAME)
