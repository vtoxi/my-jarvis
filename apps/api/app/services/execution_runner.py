from __future__ import annotations

import logging
from typing import Any

from app.core.automation_state import AutomationState
from app.core.config import Settings
from app.services.action_log import append_action_log
from app.services.hammerspoon_service import HammerspoonService
from app.services.permissions_service import NormalizedStep, RiskTier

logger = logging.getLogger(__name__)


async def run_normalized_steps(
    *,
    settings: Settings,
    automation: AutomationState,
    hs: HammerspoonService,
    steps: list[NormalizedStep],
    session_id: str,
    source: str,
) -> dict[str, Any]:
    if not automation.is_armed():
        return {"ok": False, "error": "automation_disarmed", "results": []}

    results: list[dict[str, Any]] = []
    for idx, step in enumerate(steps):
        if step.tier == RiskTier.restricted:
            append_action_log(
                settings.data_dir,
                {"event": "step_skipped_restricted", "session_id": session_id, "source": source, "index": idx, "step": step.__dict__},
            )
            results.append({"index": idx, "ok": False, "skipped": "restricted"})
            continue

        payload: dict[str, Any] = {"index": idx}
        action = step.type
        try:
            if settings.automation_sandbox:
                append_action_log(
                    settings.data_dir,
                    {
                        "event": "sandbox_exec",
                        "session_id": session_id,
                        "source": source,
                        "action": action,
                        "target": step.target,
                        "bundle_id": step.bundle_id,
                    },
                )
                results.append({"index": idx, "ok": True, "sandbox": True, "action": action})
                continue

            if action == "open_app" and step.bundle_id:
                resp = await hs.dispatch("open_app", {"bundleId": step.bundle_id})
            elif action == "focus" and step.bundle_id:
                resp = await hs.dispatch("focus", {"bundleId": step.bundle_id})
            elif action == "open_url":
                resp = await hs.dispatch("open_url", {"url": step.target})
            elif action == "delay":
                ms = int(step.meta.get("ms", step.target))
                resp = await hs.dispatch("delay", {"ms": ms})
            elif action == "tile_preset":
                resp = await hs.dispatch("tile_preset", {"preset": step.target})
            else:
                resp = await hs.dispatch("noop", {"reason": "unknown_type", "type": action})

            append_action_log(
                settings.data_dir,
                {
                    "event": "step_ok",
                    "session_id": session_id,
                    "source": source,
                    "index": idx,
                    "action": action,
                    "response": resp,
                },
            )
            results.append({"index": idx, "ok": True, "response": resp})
        except Exception as exc:  # noqa: BLE001
            logger.exception("step failed")
            automation.set_error(str(exc))
            append_action_log(
                settings.data_dir,
                {"event": "step_error", "session_id": session_id, "source": source, "index": idx, "error": str(exc)},
            )
            results.append({"index": idx, "ok": False, "error": str(exc)})
            return {"ok": False, "error": str(exc), "results": results}

    return {"ok": True, "results": results}
