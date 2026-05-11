from __future__ import annotations

import shlex
import subprocess
from fastapi import APIRouter, Body, HTTPException, Request

from app.core.config import settings
from app.schemas.sibling_projects import SiblingPathsResponse, SiblingProjectStartBody
from app.services.sibling_projects_service import jarvis_sibling_root, resolve_crewai_dir, resolve_open_interpreter_dir

router = APIRouter(tags=["sibling-projects"])


def _mgr(request: Request):
    m = getattr(request.app.state, "sibling_projects", None)
    if m is None:
        raise HTTPException(status_code=503, detail="sibling_projects_uninitialized")
    return m


def _parse_id(project_id: str) -> SiblingId:
    if project_id == "open-interpreter":
        return "open_interpreter"
    if project_id == "crewai":
        return "crewai"
    raise HTTPException(status_code=404, detail="unknown_project")


@router.get("/sibling-projects/paths", response_model=SiblingPathsResponse)
async def sibling_paths() -> SiblingPathsResponse:
    root = jarvis_sibling_root(settings)
    return SiblingPathsResponse(
        sibling_workspace_parent=str(root),
        open_interpreter_dir=str(resolve_open_interpreter_dir(settings)),
        crewai_dir=str(resolve_crewai_dir(settings)),
    )


@router.get("/sibling-projects/status")
async def sibling_status(request: Request) -> dict[str, object]:
    return _mgr(request).status()


@router.post("/sibling-projects/{project_id}/start")
async def sibling_start(
    request: Request,
    project_id: str,
    body: SiblingProjectStartBody | None = Body(default=None),
) -> dict[str, object]:
    kind = _parse_id(project_id)
    mgr = _mgr(request)
    override = body.cmd.strip() if body and body.cmd else None
    return mgr.start(kind, cmd_override=override)


@router.post("/sibling-projects/{project_id}/stop")
async def sibling_stop(request: Request, project_id: str) -> dict[str, object]:
    return _mgr(request).stop(_parse_id(project_id))


@router.post("/sibling-projects/{project_id}/probe")
async def sibling_probe(project_id: str) -> dict[str, object]:
    """Run `cmd --help` or first token `--version` in repo cwd (short, no persistent process)."""
    kind = _parse_id(project_id)
    cwd = resolve_open_interpreter_dir(settings) if kind == "open_interpreter" else resolve_crewai_dir(settings)
    if not cwd.is_dir():
        raise HTTPException(status_code=404, detail="repo_not_found")

    if kind == "open_interpreter":
        cmd = shlex.split(settings.open_interpreter_start_cmd.strip())
    else:
        cmd = shlex.split(settings.crewai_start_cmd.strip())
    if not cmd:
        raise HTTPException(status_code=400, detail="empty_cmd")

    probe = [cmd[0], "--version"] if cmd[0] != "uv" else ["uv", "--version"]
    try:
        proc = subprocess.run(
            probe,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except OSError as e:
        return {"ok": False, "detail": str(e)}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-800:],
        "stderr_tail": (proc.stderr or "")[-800:],
        "cwd": str(cwd),
        "probe": probe,
    }
