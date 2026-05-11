from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def ping(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(f"{self.base_url}/api/tags")
            res.raise_for_status()
            return res.json()

    async def list_models(self) -> list[dict[str, Any]]:
        data = await self.ping()
        models = data.get("models") or []
        out: list[dict[str, Any]] = []
        for m in models:
            name = m.get("name")
            if not name:
                continue
            out.append(
                {
                    "name": str(name),
                    "size": m.get("size"),
                    "modified_at": m.get("modified_at"),
                },
            )
        return out

    async def embed(self, *, model: str, text: str) -> list[float]:
        """POST /api/embeddings — used for local knowledge graph (Phase 8.1)."""
        prompt = (text or "")[:16_000]
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": prompt},
            )
            res.raise_for_status()
            data = res.json()
        emb = data.get("embedding")
        if not isinstance(emb, list) or not emb:
            raise ValueError("ollama embeddings: missing embedding array")
        return [float(x) for x in emb]
