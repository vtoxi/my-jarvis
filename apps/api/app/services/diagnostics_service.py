from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import aiosqlite
from fastapi import Request

from app.core.config import Settings
from app.schemas.system import SubsystemHealth, SystemHealthResponse
from app.services.slack_token_store import load_credentials
from app.services.static_analysis_runner import run_repo_checks

logger = logging.getLogger(__name__)


async def _sqlite_ok(db_path: Path) -> tuple[bool, str | None]:
    if not db_path.exists():
        return False, "database file missing"
    try:
        async with aiosqlite.connect(db_path) as db:
            cur = await db.execute("PRAGMA quick_check;")
            row = await cur.fetchone()
        val = str(row[0]) if row else ""
        if val.lower() == "ok":
            return True, None
        return False, val[:500]
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:500]


async def gather_system_health(request: Request, settings: Settings) -> SystemHealthResponse:
    t0 = time.perf_counter()
    subsystems: list[SubsystemHealth] = []
    notes: list[str] = []

    subsystems.append(SubsystemHealth(id="api", ok=True, detail="FastAPI process up"))

    ollama = getattr(request.app.state, "ollama", None)
    if ollama is None:
        subsystems.append(SubsystemHealth(id="ollama", ok=False, detail="server_state_missing"))
    else:
        t_ol = time.perf_counter()
        try:
            await ollama.ping()
            subsystems.append(
                SubsystemHealth(id="ollama", ok=True, detail="reachable", latency_ms=(time.perf_counter() - t_ol) * 1000)
            )
        except Exception as e:  # noqa: BLE001
            subsystems.append(SubsystemHealth(id="ollama", ok=False, detail=str(e)[:300]))

    slack_configured = bool(settings.slack_client_id.strip())
    try:
        creds = load_credentials(settings)
        subsystems.append(
            SubsystemHealth(
                id="slack",
                ok=creds is not None,
                detail="token present" if creds else "not connected",
                optional_for_score=not slack_configured,
            )
        )
    except Exception as e:  # noqa: BLE001
        subsystems.append(
            SubsystemHealth(id="slack", ok=False, detail=str(e)[:200], optional_for_score=not slack_configured),
        )

    hammo = getattr(request.app.state, "hammerspoon", None)
    # Mac HTTP bridge — not systemd; optional for aggregate score unless you rely on Control deck automation.
    if hammo is not None:
        t_h = time.perf_counter()
        try:
            ok = await hammo.health()
            subsystems.append(
                SubsystemHealth(
                    id="hammerspoon",
                    ok=ok,
                    detail=(
                        "bridge reachable"
                        if ok
                        else "HTTP bridge unreachable (start Hammerspoon + JARVIS bridge; not systemctl)"
                    ),
                    latency_ms=(time.perf_counter() - t_h) * 1000,
                    optional_for_score=True,
                )
            )
        except Exception as e:  # noqa: BLE001
            subsystems.append(
                SubsystemHealth(
                    id="hammerspoon",
                    ok=False,
                    detail=str(e)[:200],
                    optional_for_score=True,
                )
            )
    else:
        subsystems.append(SubsystemHealth(id="hammerspoon", ok=False, detail="not initialized", optional_for_score=True))

    sib = getattr(request.app.state, "sibling_projects", None)
    if sib is not None:
        st = sib.status()
        for key in ("open_interpreter", "crewai"):
            row = st.get(key) or {}
            running = bool(row.get("running"))
            opt = key == "crewai" or (key == "open_interpreter" and not settings.interpreter_enabled)
            detail = f"pid={row.get('pid')}" if running else f"stopped exit={row.get('exit_code')}"
            if key == "open_interpreter" and not running and not settings.interpreter_enabled:
                detail = "not started (JARVIS_INTERPRETER_ENABLED=false — start via Control / sibling API if needed)"
            subsystems.append(
                SubsystemHealth(
                    id=f"{key}_sibling",
                    ok=running,
                    detail=detail,
                    optional_for_score=opt,
                )
            )
    else:
        notes.append("sibling_projects state missing")

    intel = getattr(request.app.state, "screen_intel", None)
    if intel is not None:
        err = getattr(intel, "last_capture_error", None)
        subsystems.append(
            SubsystemHealth(
                id="screen_intel",
                ok=not bool(err),
                detail=(err or "no capture errors")[:300],
            )
        )
    else:
        subsystems.append(SubsystemHealth(id="screen_intel", ok=False, detail="state missing"))

    mem_path = settings.data_dir / "memory.sqlite3"
    ok_m, err_m = await _sqlite_ok(mem_path)
    subsystems.append(SubsystemHealth(id="memory_db", ok=ok_m, detail=err_m or "pragma quick_check ok"))

    ctx_path = settings.data_dir / "context_history.sqlite3"
    if not ctx_path.exists():
        subsystems.append(SubsystemHealth(id="context_history_db", ok=True, detail="not created yet (ok)"))
    else:
        ok_c, err_c = await _sqlite_ok(ctx_path)
        subsystems.append(SubsystemHealth(id="context_history_db", ok=ok_c, detail=err_c or "pragma quick_check ok"))

    core = [s for s in subsystems if not s.optional_for_score]
    if not core:
        health_score = 100
    else:
        n_ok_core = sum(1 for s in core if s.ok)
        health_score = int(round(100 * n_ok_core / len(core)))

    bad_core = {s.id for s in core if not s.ok}
    if not bad_core:
        status: str = "ok"
    elif "memory_db" in bad_core or "ollama" in bad_core or len(bad_core) >= 3:
        status = "critical"
    else:
        status = "degraded"

    notes = list(notes)
    notes.append(
        "health_score counts only core subsystems (excludes optional automation: Hammerspoon, CrewAI sibling; "
        "Open Interpreter sibling when JARVIS_INTERPRETER_ENABLED=false). "
        "Hammerspoon is a Mac HTTP bridge, not systemctl."
    )

    _ = time.perf_counter() - t0
    return SystemHealthResponse(status=status, health_score=health_score, subsystems=subsystems, notes=notes)


def gather_tooling_for_audit(settings: Settings, *, run_tools: bool, max_chars: int) -> dict[str, Any]:
    if not run_tools or not settings.system_allow_subprocess:
        return {"skipped": True, "reason": "set JARVIS_SYSTEM_ALLOW_SUBPROCESS=true and JARVIS_REPO_ROOT"}
    root = settings.repo_root
    if root is None:
        return {"skipped": True, "reason": "JARVIS_REPO_ROOT not set"}
    rp = Path(root).expanduser().resolve()
    if not rp.is_dir():
        return {"skipped": True, "reason": "repo root not a directory"}
    raw = run_repo_checks(repo_root=rp)
    # Trim large outputs for LLM
    for key in ("ruff", "mypy", "pytest"):
        block = raw.get(key)
        if isinstance(block, dict) and isinstance(block.get("output"), str):
            out = block["output"]
            if len(out) > max_chars:
                block["output"] = out[:max_chars] + "\n…(truncated)"
    return raw
