"""Optional background autowork loop — never raises out of the task."""

from __future__ import annotations

import asyncio
import logging

from starlette.applications import Starlette

from app.core.config import Settings
from app.services.autowork_service import run_autowork_cycle
from app.services.evolution_store import EvolutionStore

logger = logging.getLogger(__name__)


async def autowork_scheduler_loop(app: Starlette, settings: Settings) -> None:
    interval = float(settings.autowork_interval_s)
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        if not settings.autowork_enabled:
            continue
        store = getattr(app.state, "evolution", None)
        try:
            summary = await asyncio.to_thread(run_autowork_cycle, settings)
        except Exception:  # noqa: BLE001
            logger.exception("autowork scheduled tick thread failed")
            continue
        if isinstance(store, EvolutionStore):
            try:
                await store.append_event(
                    kind="autowork_tick",
                    payload={"ok": summary.get("ok"), "elapsed_s": summary.get("elapsed_s"), "restart_requested": summary.get("restart_requested")},
                )
            except Exception:  # noqa: BLE001
                logger.exception("autowork append_event failed")
