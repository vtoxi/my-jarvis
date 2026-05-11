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
