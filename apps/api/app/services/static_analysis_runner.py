from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_OUTPUT = 120_000
_DEFAULT_TIMEOUT_S = 120


def _run(cmd: list[str], *, cwd: Path, timeout_s: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        out = (p.stdout or "") + ("\n--- stderr ---\n" + p.stderr if p.stderr else "")
        if len(out) > _MAX_OUTPUT:
            out = out[:_MAX_OUTPUT] + "\n…(truncated)"
        return {
            "ok": p.returncode == 0,
            "exit_code": p.returncode,
            "output": out,
            "elapsed_s": round(time.monotonic() - started, 2),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "output": "timeout", "elapsed_s": timeout_s}
    except Exception as e:  # noqa: BLE001
        logger.exception("static analysis subprocess")
        return {"ok": False, "exit_code": None, "output": str(e), "elapsed_s": round(time.monotonic() - started, 2)}


def run_repo_checks(
    *,
    repo_root: Path,
    run_pytest: bool = True,
    run_ruff: bool = True,
    run_mypy: bool = True,
    api_dir: Path | None = None,
) -> dict[str, Any]:
    """Run ruff, mypy, pytest under apps/api when repo_root is the monorepo root."""
    root = repo_root.resolve()
    api = (api_dir or (root / "apps" / "api")).resolve()
    if not api.is_dir():
        return {"error": "apps/api not found under repo root", "repo_root": str(root)}
    results: dict[str, Any] = {"repo_root": str(root), "api_dir": str(api)}
    if run_ruff and shutil.which("ruff"):
        results["ruff"] = _run(["ruff", "check", "."], cwd=api, timeout_s=_DEFAULT_TIMEOUT_S)
    else:
        results["ruff"] = {"skipped": True, "reason": "ruff not on PATH"}
    if run_mypy and shutil.which("mypy"):
        results["mypy"] = _run(["mypy", "app"], cwd=api, timeout_s=_DEFAULT_TIMEOUT_S)
    else:
        results["mypy"] = {"skipped": True, "reason": "mypy not on PATH"}
    if run_pytest and shutil.which("pytest"):
        results["pytest"] = _run(["pytest", "-q", "--tb=no"], cwd=api, timeout_s=_DEFAULT_TIMEOUT_S)
    else:
        results["pytest"] = {"skipped": True, "reason": "pytest not on PATH"}
    return results
