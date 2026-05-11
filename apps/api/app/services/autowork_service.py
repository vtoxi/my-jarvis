"""
Bounded self-maintenance for my-jarvis: diagnostics, optional installs/fixes, restart *request* file.

- Never kills or restarts the API process from inside itself.
- Never applies git patches without the existing Phase 6 token flow.
- All heavy steps are opt-in via settings and require JARVIS_SYSTEM_ALLOW_SUBPROCESS where subprocesses run.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import shutil

from app.core.config import Settings
from app.services.static_analysis_runner import _run, run_repo_checks

logger = logging.getLogger(__name__)


def _api_dir(settings: Settings) -> Path | None:
    if settings.repo_root is None:
        return None
    api = Path(settings.repo_root).expanduser().resolve() / "apps" / "api"
    return api if api.is_dir() else None


def _desktop_dir(settings: Settings) -> Path | None:
    if settings.repo_root is None:
        return None
    d = Path(settings.repo_root).expanduser().resolve() / "apps" / "desktop"
    return d if d.is_dir() else None


def _repo_checks_green(raw: dict[str, Any]) -> bool:
    if raw.get("error"):
        return False
    saw_run = False
    for key in ("ruff", "mypy", "pytest"):
        block = raw.get(key)
        if not isinstance(block, dict):
            continue
        if block.get("skipped"):
            continue
        saw_run = True
        if not block.get("ok"):
            return False
    return saw_run


def _write_last_run(settings: Settings, payload: dict[str, Any]) -> None:
    root = settings.data_dir / "autowork"
    root.mkdir(parents=True, exist_ok=True)
    p = root / "last_run.json"
    payload = {**payload, "written_at_unix": time.time()}
    p.write_text(json.dumps(payload, indent=2)[:200_000], encoding="utf-8")


def _write_restart_request(settings: Settings, *, reason: str, summary: dict[str, Any]) -> None:
    root = settings.data_dir / "autowork"
    root.mkdir(parents=True, exist_ok=True)
    p = root / "RESTART_REQUESTED.json"
    doc = {
        "requested_at_unix": time.time(),
        "reason": reason[:2000],
        "note": (
            "JARVIS does not restart uvicorn from inside the API. "
            "Use your process manager or: stop the server, then start it again after reviewing autowork output."
        ),
        "summary_head": json.dumps(summary, default=str)[:8000],
    }
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    logger.warning("autowork wrote RESTART_REQUESTED.json — operator should restart the API process manually")


def run_autowork_cycle(settings: Settings) -> dict[str, Any]:
    """Synchronous cycle; swallow all errors into the returned dict (scheduler must not crash)."""
    t0 = time.perf_counter()
    out: dict[str, Any] = {"ok": True, "steps": [], "restart_requested": False}
    try:
        if not settings.autowork_enabled:
            return {"ok": False, "error": "JARVIS_AUTOWORK_ENABLED=false", "steps": []}

        allow = bool(settings.system_allow_subprocess)
        api_dir = _api_dir(settings)

        if settings.repo_root and allow:
            root = Path(settings.repo_root).expanduser().resolve()
            raw = run_repo_checks(repo_root=root, run_pytest=True, run_ruff=True, run_mypy=True)
            out["steps"].append({"name": "repo_checks", "result": raw})
            green = _repo_checks_green(raw)
            out["repo_checks_green"] = green
        elif settings.repo_root:
            out["steps"].append(
                {"name": "repo_checks", "skipped": True, "reason": "JARVIS_SYSTEM_ALLOW_SUBPROCESS=false"},
            )
            out["repo_checks_green"] = False
        else:
            out["steps"].append({"name": "repo_checks", "skipped": True, "reason": "JARVIS_REPO_ROOT unset"})
            out["repo_checks_green"] = False

        if allow and settings.autowork_poetry_install and api_dir:
            if shutil.which("poetry"):
                r = _run(["poetry", "install", "--no-interaction"], cwd=api_dir, timeout_s=min(900, settings.autowork_subprocess_timeout_s))
                out["steps"].append({"name": "poetry_install_api", "result": r})
            else:
                out["steps"].append({"name": "poetry_install_api", "skipped": True, "reason": "poetry not on PATH"})

        if allow and settings.autowork_ruff_autofix and api_dir:
            if shutil.which("ruff"):
                r = _run(["ruff", "check", ".", "--fix"], cwd=api_dir, timeout_s=min(300, settings.autowork_subprocess_timeout_s))
                out["steps"].append({"name": "ruff_autofix_api", "result": r})
            else:
                out["steps"].append({"name": "ruff_autofix_api", "skipped": True, "reason": "ruff not on PATH"})

        desk = _desktop_dir(settings)
        if allow and settings.autowork_npm_build and desk:
            if shutil.which("npm"):
                r = _run(["npm", "run", "build"], cwd=desk, timeout_s=min(900, settings.autowork_subprocess_timeout_s))
                out["steps"].append({"name": "npm_build_desktop", "result": r})
            else:
                out["steps"].append({"name": "npm_build_desktop", "skipped": True, "reason": "npm not on PATH"})

        raw_summary = next((s["result"] for s in out["steps"] if s.get("name") == "repo_checks" and isinstance(s.get("result"), dict)), None)
        if (
            settings.autowork_restart_request_on_green
            and isinstance(raw_summary, dict)
            and _repo_checks_green(raw_summary)
        ):
            _write_restart_request(settings, reason="repo_checks all non-skipped tools passed", summary=out)
            out["restart_requested"] = True

        out["elapsed_s"] = round(time.perf_counter() - t0, 2)
        _write_last_run(settings, out)
        return out
    except Exception as e:  # noqa: BLE001
        logger.exception("autowork cycle")
        out["ok"] = False
        out["error"] = str(e)[:4000]
        out["elapsed_s"] = round(time.perf_counter() - t0, 2)
        _write_last_run(settings, out)
        return out
