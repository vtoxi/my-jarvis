from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.system_evolution_store import SystemEvolutionStore
from app.services.system_patch_approval import (
    mint_patch_apply_token,
    mint_rollback_token,
    verify_patch_apply_token,
    verify_rollback_token,
)

logger = logging.getLogger(__name__)

_DIFF_PATH_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$")


def paths_from_unified_diff(diff_text: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for line in diff_text.splitlines():
        m = _DIFF_PATH_RE.match(line.strip())
        if not m:
            continue
        b = m.group(2).strip()
        if b and b not in seen:
            seen.add(b)
            paths.append(b)
    return paths


def _run_git(args: list[str], *, cwd: Path, timeout_s: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def _git_clean(repo: Path) -> tuple[bool, str]:
    p = _run_git(["git", "status", "--porcelain"], cwd=repo, timeout_s=30.0)
    if p.returncode != 0:
        return False, (p.stderr or p.stdout or "git status failed")[:500]
    if (p.stdout or "").strip():
        return False, "working tree not clean — commit or stash before patch apply"
    return True, ""


def _head_sha(repo: Path) -> str | None:
    p = _run_git(["git", "rev-parse", "HEAD"], cwd=repo, timeout_s=30.0)
    if p.returncode != 0:
        return None
    return (p.stdout or "").strip()


def _head_branch(repo: Path) -> str:
    p = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, timeout_s=30.0)
    if p.returncode != 0:
        return "HEAD"
    return (p.stdout or "").strip()


def prepare_patch(
    settings: Settings,
    *,
    diff_text: str,
    branch_suffix: str | None,
) -> dict[str, Any]:
    if settings.repo_root is None:
        raise ValueError("JARVIS_REPO_ROOT not set")
    repo = Path(settings.repo_root).expanduser().resolve()
    if not (repo / ".git").is_dir():
        raise ValueError("repo_root is not a git checkout")
    clean_ok, msg = _git_clean(repo)
    if not clean_ok:
        raise ValueError(msg)
    base_sha = _head_sha(repo)
    if not base_sha:
        raise ValueError("could not read HEAD")
    suf = (branch_suffix or "").strip() or time.strftime("%Y%m%d%H%M%S", time.gmtime())
    branch_name = f"jarvis-evolve-{suf}"[:120]
    diff_sha = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    patch_dir = settings.data_dir / "system" / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    pid = str(uuid.uuid4())
    patch_file = patch_dir / f"{pid}.patch"
    patch_file.write_text(diff_text, encoding="utf-8")
    chk = subprocess.run(
        ["git", "apply", "--check", str(patch_file)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=120.0,
    )
    if chk.returncode != 0:
        try:
            patch_file.unlink(missing_ok=True)
        except OSError:
            pass
        err = (chk.stderr or chk.stdout or "git apply --check failed")[:2000]
        raise ValueError(err)
    return {
        "patch_id": pid,
        "branch_name": branch_name,
        "base_sha": base_sha,
        "diff_sha256": diff_sha,
        "preview_lines": len(diff_text.splitlines()),
        "patch_file": str(patch_file),
    }


async def persist_prepare_row(
    store: SystemEvolutionStore,
    *,
    patch_id: str,
    branch_name: str,
    base_sha: str,
    diff_sha256: str,
    diff_preview: str,
) -> None:
    await store.insert_patch_proposal(
        proposal_id=patch_id,
        status="pending",
        branch_name=branch_name,
        base_sha=base_sha,
        diff_sha256=diff_sha256,
        diff_preview=diff_preview[:16_000],
    )


def mint_apply_token_for_prepare(settings: Settings, prep: dict[str, Any], diff_text: str) -> tuple[str, int]:
    return mint_patch_apply_token(
        settings,
        patch_id=prep["patch_id"],
        diff_text=diff_text,
        branch_name=prep["branch_name"],
        base_sha=prep["base_sha"],
    )


async def apply_patch(
    settings: Settings,
    store: SystemEvolutionStore,
    *,
    token: str,
    diff_text: str,
) -> dict[str, Any]:
    if not settings.system_patches_enabled:
        return {"ok": False, "message": "JARVIS_SYSTEM_PATCHES_ENABLED is not true", "pytest_exit_code": None}
    if settings.repo_root is None:
        return {"ok": False, "message": "JARVIS_REPO_ROOT not set", "pytest_exit_code": None}
    try:
        payload = verify_patch_apply_token(settings, token=token, diff_text=diff_text)
    except ValueError as e:
        return {"ok": False, "message": str(e), "pytest_exit_code": None}

    row = await store.get_patch_proposal(payload.patch_id)
    if not row or row.get("diff_sha256") != payload.diff_sha256:
        return {"ok": False, "message": "patch proposal missing or diff mismatch", "pytest_exit_code": None}
    if row.get("status") != "pending":
        return {"ok": False, "message": f"patch not pending (status={row.get('status')})", "pytest_exit_code": None}

    repo = Path(settings.repo_root).expanduser().resolve()
    patch_file = Path(settings.data_dir) / "system" / "patches" / f"{payload.patch_id}.patch"
    if not patch_file.is_file():
        return {"ok": False, "message": "patch file missing on disk", "pytest_exit_code": None}

    clean_ok, msg = _git_clean(repo)
    if not clean_ok:
        return {"ok": False, "message": msg, "pytest_exit_code": None}
    head = _head_sha(repo)
    if head != payload.base_sha:
        return {"ok": False, "message": "HEAD moved since prepare; re-run prepare", "pytest_exit_code": None}

    prev_branch = _head_branch(repo)
    br = _run_git(["git", "checkout", "-b", payload.branch_name], cwd=repo, timeout_s=60.0)
    if br.returncode != 0:
        return {
            "ok": False,
            "message": (br.stderr or br.stdout or "checkout -b failed")[:2000],
            "pytest_exit_code": None,
        }

    def _cleanup_branch() -> None:
        _run_git(["git", "checkout", prev_branch], cwd=repo, timeout_s=60.0)
        _run_git(["git", "branch", "-D", payload.branch_name], cwd=repo, timeout_s=60.0)

    ap = subprocess.run(
        ["git", "apply", str(patch_file)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=120.0,
    )
    if ap.returncode != 0:
        _cleanup_branch()
        err = (ap.stderr or ap.stdout or "git apply failed")[:2000]
        await store.update_patch_proposal(
            payload.patch_id,
            status="failed",
            outcome_text=err,
        )
        return {"ok": False, "message": err, "pytest_exit_code": None, "patch_id": payload.patch_id}

    api_dir = repo / "apps" / "api"
    pytest_code: int | None = None
    if api_dir.is_dir() and shutil.which("pytest"):
        pt = subprocess.run(
            ["pytest", "-q", "--tb=no"],
            cwd=str(api_dir),
            capture_output=True,
            text=True,
            timeout=600.0,
        )
        pytest_code = pt.returncode
        if pt.returncode != 0:
            rev = subprocess.run(
                ["git", "apply", "--reverse", str(patch_file)],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=120.0,
            )
            if rev.returncode != 0:
                logger.error("git apply --reverse failed after pytest failure: %s", rev.stderr)
            _cleanup_branch()
            tail = (pt.stdout or "") + (pt.stderr or "")
            if len(tail) > 4000:
                tail = tail[:4000] + "…"
            await store.update_patch_proposal(
                payload.patch_id,
                status="failed",
                outcome_text=f"pytest exit {pt.returncode}\n{tail}",
            )
            return {
                "ok": False,
                "message": "pytest failed; patch reversed and branch removed",
                "pytest_exit_code": pytest_code,
                "patch_id": payload.patch_id,
            }

    manifest = {
        "patch_file": str(patch_file),
        "prev_branch": prev_branch,
        "new_branch": payload.branch_name,
        "paths": paths_from_unified_diff(diff_text),
    }
    await store.update_patch_proposal(
        payload.patch_id,
        status="applied",
        manifest_json=json.dumps(manifest, separators=(",", ":")),
        outcome_text="applied and pytest passed",
        applied_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    return {
        "ok": True,
        "message": f"applied on branch {payload.branch_name}; pytest exit {pytest_code}",
        "pytest_exit_code": pytest_code,
        "patch_id": payload.patch_id,
    }


def mint_rollback_for_patch(settings: Settings, *, patch_id: str, base_sha: str) -> tuple[str, int]:
    return mint_rollback_token(settings, patch_id=patch_id, base_sha=base_sha)


async def apply_rollback(
    settings: Settings,
    store: SystemEvolutionStore,
    *,
    token: str,
    patch_id: str,
) -> dict[str, Any]:
    if not settings.system_patches_enabled:
        return {"ok": False, "message": "JARVIS_SYSTEM_PATCHES_ENABLED is not true"}
    if settings.repo_root is None:
        return {"ok": False, "message": "JARVIS_REPO_ROOT not set"}
    try:
        rb = verify_rollback_token(settings, token=token, patch_id=patch_id)
    except ValueError as e:
        return {"ok": False, "message": str(e)}

    row = await store.get_patch_proposal(rb.patch_id)
    if not row or row.get("status") != "applied":
        return {"ok": False, "message": "patch not in applied state"}
    if str(row.get("base_sha") or "") != rb.base_sha:
        return {"ok": False, "message": "base_sha mismatch"}
    manifest = row.get("manifest") or {}
    patch_file = manifest.get("patch_file")
    prev_branch = manifest.get("prev_branch")
    new_branch = manifest.get("new_branch")
    if not patch_file or not prev_branch or not new_branch:
        return {"ok": False, "message": "manifest incomplete"}

    repo = Path(settings.repo_root).expanduser().resolve()
    pf = Path(patch_file)
    if not pf.is_file():
        return {"ok": False, "message": "patch file missing for rollback"}

    cur = _head_branch(repo)
    if cur != str(new_branch):
        return {"ok": False, "message": f"expected to be on branch {new_branch}, on {cur}"}

    rev = subprocess.run(
        ["git", "apply", "--reverse", str(pf)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=120.0,
    )
    if rev.returncode != 0:
        return {"ok": False, "message": (rev.stderr or rev.stdout or "reverse apply failed")[:2000]}

    _run_git(["git", "checkout", str(prev_branch)], cwd=repo, timeout_s=60.0)
    _run_git(["git", "branch", "-D", str(new_branch)], cwd=repo, timeout_s=60.0)

    await store.update_patch_proposal(
        patch_id,
        status="rolled_back",
        rolled_back_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        outcome_text=(row.get("outcome_text") or "") + " | rolled back",
    )
    return {"ok": True, "message": "rollback complete"}
