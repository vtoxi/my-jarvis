"""Sandbox repo benchmark — reuses Phase 6 static_analysis_runner (ruff/mypy/pytest) behind env gates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.static_analysis_runner import run_repo_checks

logger = logging.getLogger(__name__)


def run_sandbox_benchmark(settings: Settings) -> dict[str, Any]:
    if settings.repo_root is None:
        return {"ok": False, "skipped": True, "reason": "JARVIS_REPO_ROOT not set"}
    if not settings.system_allow_subprocess:
        return {"ok": False, "skipped": True, "reason": "JARVIS_SYSTEM_ALLOW_SUBPROCESS=false"}
    root = Path(settings.repo_root).expanduser().resolve()
    if not root.is_dir():
        return {"ok": False, "skipped": True, "reason": "repo root is not a directory"}
    raw = run_repo_checks(repo_root=root, run_pytest=True, run_ruff=True, run_mypy=True)
    if raw.get("error"):
        return {"ok": False, "skipped": True, "reason": str(raw.get("error")), "repo_root": str(root)}

    def _block_ok(block: dict[str, Any]) -> bool:
        if block.get("skipped"):
            return True
        return bool(block.get("ok"))

    pytest_b = raw.get("pytest") or {}
    ruff_b = raw.get("ruff") or {}
    mypy_b = raw.get("mypy") or {}
    all_ok = _block_ok(pytest_b) and _block_ok(ruff_b) and _block_ok(mypy_b)

    summary = {
        "pytest": {
            "skipped": bool(pytest_b.get("skipped")),
            "ok": pytest_b.get("ok"),
            "exit_code": pytest_b.get("exit_code"),
            "elapsed_s": pytest_b.get("elapsed_s"),
        },
        "ruff": {
            "skipped": bool(ruff_b.get("skipped")),
            "ok": ruff_b.get("ok"),
            "exit_code": ruff_b.get("exit_code"),
            "elapsed_s": ruff_b.get("elapsed_s"),
        },
        "mypy": {
            "skipped": bool(mypy_b.get("skipped")),
            "ok": mypy_b.get("ok"),
            "exit_code": mypy_b.get("exit_code"),
            "elapsed_s": mypy_b.get("elapsed_s"),
        },
    }
    logger.info(
        "sandbox benchmark repo=%s summary_ok=%s pytest_ok=%s ruff_ok=%s mypy_ok=%s",
        root,
        all_ok,
        summary["pytest"].get("ok"),
        summary["ruff"].get("ok"),
        summary["mypy"].get("ok"),
    )
    return {"ok": all_ok, "skipped": False, "repo_root": str(root), "summary": summary, "raw": raw}


def compact_benchmark_for_event(res: dict[str, Any]) -> dict[str, Any]:
    """Strip large tool outputs before SQLite evolution_events."""
    if res.get("skipped"):
        return {"skipped": True, "reason": res.get("reason"), "ok": bool(res.get("ok"))}
    raw = res.get("raw") or {}
    compact: dict[str, Any] = {"ok": res.get("ok"), "repo_root": res.get("repo_root"), "summary": res.get("summary")}
    for key in ("ruff", "mypy", "pytest"):
        block = raw.get(key)
        if not isinstance(block, dict):
            continue
        out = str(block.get("output") or "")
        compact[key] = {
            "skipped": block.get("skipped"),
            "ok": block.get("ok"),
            "exit_code": block.get("exit_code"),
            "elapsed_s": block.get("elapsed_s"),
            "output_head": out[:4000],
        }
    return compact
