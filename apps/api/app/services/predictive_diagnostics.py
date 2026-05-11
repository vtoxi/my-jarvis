from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import Request

from app.core.config import Settings
from app.services.slack_token_store import load_credentials


def build_predictions(*, request: Request, settings: Settings) -> list[dict[str, Any]]:
    """
    Lightweight heuristics only — no external API calls. Not prophecy; operator hints.
    """
    out: list[dict[str, Any]] = []
    mem = settings.data_dir / "memory.sqlite3"
    if mem.exists():
        age_s = time.time() - mem.stat().st_mtime
        if age_s > 86400 * 30:
            out.append(
                {
                    "id": "memory_stale",
                    "severity": "low",
                    "title": "Memory database quiet for 30+ days",
                    "detail": "If you expected active sessions, verify backups and disk.",
                }
            )

    ctx = settings.data_dir / "context_history.sqlite3"
    if ctx.exists():
        sz = ctx.stat().st_size
        if sz > 80 * 1024 * 1024:
            out.append(
                {
                    "id": "context_db_large",
                    "severity": "medium",
                    "title": "Context history file is large",
                    "detail": "Consider pruning old snapshots from Evolution Lab when comfortable.",
                }
            )

    try:
        creds = load_credentials(settings)
        if creds:
            out.append(
                {
                    "id": "slack_token_age",
                    "severity": "info",
                    "title": "Slack installation present",
                    "detail": "Re-auth via Slack hub if the workspace revokes the bot or scopes change.",
                }
            )
    except Exception:  # noqa: BLE001
        pass

    sib = getattr(request.app.state, "sibling_projects", None)
    if sib is not None:
        st = sib.status()
        oi = st.get("open_interpreter") or {}
        if settings.interpreter_enabled and not oi.get("running"):
            out.append(
                {
                    "id": "interpreter_expected_down",
                    "severity": "medium",
                    "title": "Interpreter enabled but sibling not running",
                    "detail": "Start from Control deck or sibling API before automation that depends on it.",
                }
            )

    return out[:24]


def strategic_maturity_index(*, twin_payload: dict[str, Any], idle_run_count: int) -> int:
    """Heuristic 0–100: twin meta confidence + idle learning cadence."""
    meta = twin_payload.get("meta") or {}
    conf = meta.get("confidence_by_dimension") or {}
    scores = [float(v) for v in conf.values() if isinstance(v, (int, float))]
    base = int(round(100 * (sum(scores) / max(1, len(scores))))) if scores else 20
    bonus = min(25, idle_run_count * 3)
    return max(0, min(100, base + bonus))
