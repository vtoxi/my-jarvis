from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.deps import get_ollama
from app.services.ollama_client import OllamaClient
from app.schemas.models import ModelsResponse, OllamaModelInfo

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelsResponse)
async def list_models(
    active_model: str | None = Query(default=None, description="Currently selected model tag"),
    ollama: OllamaClient = Depends(get_ollama),
) -> ModelsResponse:
    active = (active_model or settings.default_ollama_model).strip()
    try:
        raw = await ollama.list_models()
        installed = [OllamaModelInfo(name=m["name"], size=m.get("size"), modified_at=m.get("modified_at")) for m in raw]
        return ModelsResponse(
            ollama_reachable=True,
            ollama_error=None,
            active_model=active,
            installed=installed,
        )
    except Exception as exc:  # noqa: BLE001
        return ModelsResponse(
            ollama_reachable=False,
            ollama_error=str(exc),
            active_model=active,
            installed=[],
        )
