from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.knowledge_embedding import deterministic_embedding
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


async def embed_for_knowledge(settings: Settings, ollama: OllamaClient | None, text: str) -> list[float]:
    if settings.llm_stub:
        return deterministic_embedding(text)
    if ollama is None:
        return deterministic_embedding(text)
    model = (settings.evolution_knowledge_embed_model or settings.default_ollama_model).strip()
    if not model:
        return deterministic_embedding(text)
    try:
        return await ollama.embed(model=model, text=text)
    except Exception as e:  # noqa: BLE001
        logger.warning("ollama embed failed; using deterministic fallback: %s", e)
        return deterministic_embedding(text)
