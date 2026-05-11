"""Optional asyncio-based idle learning loop (Phase 8.1).

No APScheduler dependency — one background task, cancellable on shutdown.
Opt-in via JARVIS_EVOLUTION_IDLE_SCHEDULE_ENABLED; still requires JARVIS_EVOLUTION_IDLE_ENABLED.
"""

from __future__ import annotations

import asyncio
import logging

from starlette.applications import Starlette

from app.core.config import Settings
from app.services.evolution_store import EvolutionStore
from app.services.idle_learning_service import run_idle_cycle

logger = logging.getLogger(__name__)


async def evolution_idle_scheduler_loop(app: Starlette, settings: Settings) -> None:
    interval = float(settings.evolution_idle_schedule_interval_s)
    while True:
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        store = getattr(app.state, "evolution", None)
        if not isinstance(store, EvolutionStore):
            logger.warning("evolution store missing — idle scheduler stopping")
            return
        if not settings.evolution_idle_enabled:
            continue
        try:
            await run_idle_cycle(app=app, settings=settings, store=store)
        except ValueError as e:
            logger.info("scheduled idle skipped: %s", e)
        except Exception:  # noqa: BLE001
            logger.exception("scheduled idle learning tick failed")
