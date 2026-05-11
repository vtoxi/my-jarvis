from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class HammerspoonService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(
                    f"{self._settings.hammerspoon_url.rstrip('/')}/health",
                    headers={"Authorization": f"Bearer {self._settings.hammerspoon_token}"},
                )
                return res.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.debug("hammerspoon health failed: %s", exc)
            return False

    async def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"action": action, **payload}
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{self._settings.hammerspoon_url.rstrip('/')}/jarvis",
                json=body,
                headers={"Authorization": f"Bearer {self._settings.hammerspoon_token}"},
            )
            res.raise_for_status()
            return res.json()
