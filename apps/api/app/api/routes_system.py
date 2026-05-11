from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.schemas.system import (
    IncidentRecord,
    SystemAuditRequest,
    SystemAuditResponse,
    SystemErrorsResponse,
    SystemHealthResponse,
    SystemLogsResponse,
    SystemPatchApplyRequest,
    SystemPatchApplyResponse,
    SystemPatchPrepareRequest,
    SystemPatchPrepareResponse,
    SystemPerformanceResponse,
    SystemRepairRequest,
    SystemRepairResponse,
    SystemRollbackPrepareRequest,
    SystemRollbackPrepareResponse,
    SystemRollbackRequest,
    SystemRollbackResponse,
)
from app.services.code_audit_crew_runner import run_code_audit_crew
from app.services.diagnostics_service import gather_system_health, gather_tooling_for_audit
from app.services.patch_service import apply_patch, mint_apply_token_for_prepare, persist_prepare_row, prepare_patch
from app.services.performance_monitor import collect_performance_metrics
from app.services.rollback_service import apply_rollback, mint_rollback_for_patch
from app.services.self_healing_crew_runner import run_self_healing_crew

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system", "phase6"])


def _evo(request: Request) -> Any:
    st = getattr(request.app.state, "system_evolution", None)
    if st is None:
        raise HTTPException(status_code=503, detail="System evolution store not initialized")
    return st


def _tail_log_file(path: Path | None, *, max_lines: int) -> tuple[list[str], bool]:
    if path is None or not path.is_file():
        return [], False
    try:
        sz = path.stat().st_size
        chunk = min(sz, 512_000)
        with open(path, "rb") as f:
            if sz > chunk:
                f.seek(-chunk, os.SEEK_END)
            raw = f.read().decode("utf-8", errors="replace")
    except OSError:
        return [], False
    lines = raw.splitlines()
    truncated = len(lines) > max_lines
    return lines[-max_lines:], truncated


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health(request: Request) -> SystemHealthResponse:
    return await gather_system_health(request, settings)


@router.get("/system/errors", response_model=SystemErrorsResponse)
async def system_errors(request: Request, limit: int = 50) -> SystemErrorsResponse:
    store = _evo(request)
    rows = await store.list_incidents(limit=min(limit, 200))
    log_path = getattr(request.app.state, "api_log_path", None)
    incidents = [
        IncidentRecord(
            id=r["id"],
            created_at=r["created_at"],
            severity=r["severity"],
            subsystem=r.get("subsystem"),
            summary=r["summary"],
            detail=r.get("detail") or {},
            repair_output=r.get("repair_output"),
        )
        for r in rows
    ]
    hint = str(log_path) if isinstance(log_path, Path) else None
    return SystemErrorsResponse(incidents=incidents, log_tail_hint=hint)


@router.get("/system/logs", response_model=SystemLogsResponse)
async def system_logs(request: Request, lines: int = 120) -> SystemLogsResponse:
    log_path = getattr(request.app.state, "api_log_path", None)
    n = max(10, min(500, lines))
    tail, truncated = _tail_log_file(log_path if isinstance(log_path, Path) else None, max_lines=n)
    return SystemLogsResponse(
        path=str(log_path) if isinstance(log_path, Path) else None,
        lines=tail,
        truncated=truncated,
    )


@router.get("/system/performance", response_model=SystemPerformanceResponse)
async def system_performance() -> SystemPerformanceResponse:
    data = collect_performance_metrics(metrics_enabled=bool(settings.system_metrics_enabled))
    if not data.get("available"):
        return SystemPerformanceResponse(
            available=False,
            error=str(data.get("error") or "unavailable"),
        )
    return SystemPerformanceResponse(
        available=True,
        cpu_percent=data.get("cpu_percent"),
        ram_used_mb=data.get("ram_used_mb"),
        ram_total_mb=data.get("ram_total_mb"),
        collected_at_unix=data.get("collected_at_unix"),
    )


@router.post("/system/repair", response_model=SystemRepairResponse)
async def system_repair(request: Request, body: SystemRepairRequest) -> SystemRepairResponse:
    store = _evo(request)
    health = await gather_system_health(request, settings)
    health_json = health.model_dump_json()
    log_path = getattr(request.app.state, "api_log_path", None)
    tail, _ = _tail_log_file(log_path if isinstance(log_path, Path) else None, max_lines=160)
    log_tail = "\n".join(tail)

    def work() -> Any:
        return run_self_healing_crew(
            settings=settings,
            health_json=health_json,
            log_tail=log_tail,
            operator_context=body.context,
            model=settings.default_ollama_model,
        )

    try:
        result = await anyio.to_thread.run_sync(work)
    except Exception as e:
        logger.exception("self-healing crew")
        raise HTTPException(status_code=502, detail=str(e)) from e

    detail = {
        "health_status": health.status,
        "health_score": health.health_score,
        "subsystems": [s.model_dump() for s in health.subsystems],
    }
    repair_out = {
        "root_cause_hypothesis": result.root_cause_hypothesis,
        "severity": result.severity,
        "recommended_commands": result.recommended_commands,
        "patch_plan": result.patch_plan,
        "raw_markdown": result.raw_markdown[:12000],
    }
    iid = await store.insert_incident(
        severity=result.severity,
        subsystem=None,
        summary=result.user_visible_summary[:500],
        detail=detail,
        repair_output=repair_out,
    )
    return SystemRepairResponse(
        incident_id=iid,
        requires_human_approval=True,
        root_cause_hypothesis=result.root_cause_hypothesis,
        severity=result.severity,
        user_visible_summary=result.user_visible_summary,
        recommended_commands=result.recommended_commands,
        patch_plan=result.patch_plan,
        raw_markdown=result.raw_markdown,
    )


@router.post("/system/audit", response_model=SystemAuditResponse)
async def system_audit(request: Request, body: SystemAuditRequest) -> SystemAuditResponse:
    store = _evo(request)
    tools = gather_tooling_for_audit(settings, run_tools=body.run_tools, max_chars=body.max_tool_output_chars)
    if body.run_tools and tools.get("skipped"):
        logger.info("audit tools skipped: %s", tools.get("reason"))

    def work() -> Any:
        return run_code_audit_crew(
            settings=settings,
            tools_summary=tools,
            mode=body.mode,
            model=settings.default_ollama_model,
        )

    try:
        result = await anyio.to_thread.run_sync(work)
    except Exception as e:
        logger.exception("code audit crew")
        raise HTTPException(status_code=502, detail=str(e)) from e

    aid = await store.insert_audit_run(
        mode=body.mode,
        tools=tools,
        synthesis=result.synthesis_markdown[:24000],
        debt_score=result.debt_score,
    )
    return SystemAuditResponse(
        audit_id=aid,
        mode=body.mode,
        tools=tools,
        debt_score=result.debt_score,
        synthesis_markdown=result.synthesis_markdown,
        categories=result.categories,
    )


@router.post("/system/improve", response_model=SystemAuditResponse)
async def system_improve(request: Request, body: SystemAuditRequest) -> SystemAuditResponse:
    body2 = body.model_copy(update={"mode": "improve"})
    return await system_audit(request, body2)


@router.get("/system/patch/queue")
async def system_patch_queue(request: Request, limit: int = 30) -> dict[str, Any]:
    store = _evo(request)
    rows = await store.list_patch_proposals(limit=min(limit, 100))
    return {"patches": rows}


@router.post("/system/improve/prepare", response_model=SystemPatchPrepareResponse)
async def system_improve_prepare(request: Request, body: SystemPatchPrepareRequest) -> SystemPatchPrepareResponse:
    store = _evo(request)
    try:
        prep = prepare_patch(settings, diff_text=body.diff_text, branch_suffix=body.branch_suffix)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    preview = "\n".join(body.diff_text.splitlines()[:40])
    await persist_prepare_row(
        store,
        patch_id=prep["patch_id"],
        branch_name=prep["branch_name"],
        base_sha=prep["base_sha"],
        diff_sha256=prep["diff_sha256"],
        diff_preview=preview,
    )
    token, exp = mint_apply_token_for_prepare(settings, prep, body.diff_text)
    return SystemPatchPrepareResponse(
        patch_id=prep["patch_id"],
        approval_token=token,
        expires_at_unix=exp,
        branch_name=prep["branch_name"],
        base_sha=prep["base_sha"],
        diff_sha256=prep["diff_sha256"],
        preview_lines=prep["preview_lines"],
    )


@router.post("/system/improve/apply", response_model=SystemPatchApplyResponse)
async def system_improve_apply(request: Request, body: SystemPatchApplyRequest) -> SystemPatchApplyResponse:
    store = _evo(request)
    res = await apply_patch(settings, store, token=body.approval_token, diff_text=body.diff_text)
    return SystemPatchApplyResponse(
        ok=res["ok"],
        patch_id=str(res.get("patch_id") or ""),
        message=res["message"],
        pytest_exit_code=res.get("pytest_exit_code"),
    )


@router.post("/system/rollback/prepare", response_model=SystemRollbackPrepareResponse)
async def system_rollback_prepare(request: Request, body: SystemRollbackPrepareRequest) -> SystemRollbackPrepareResponse:
    store = _evo(request)
    row = await store.get_patch_proposal(body.patch_id)
    if not row or row.get("status") != "applied":
        raise HTTPException(status_code=400, detail="patch not in applied state")
    base_sha = str(row.get("base_sha") or "")
    if not base_sha:
        raise HTTPException(status_code=400, detail="missing base_sha")
    token, exp = mint_rollback_for_patch(settings, patch_id=body.patch_id, base_sha=base_sha)
    return SystemRollbackPrepareResponse(approval_token=token, expires_at_unix=exp, patch_id=body.patch_id)


@router.post("/system/rollback", response_model=SystemRollbackResponse)
async def system_rollback(request: Request, body: SystemRollbackRequest) -> SystemRollbackResponse:
    store = _evo(request)
    res = await apply_rollback(settings, store, token=body.approval_token, patch_id=body.patch_id)
    return SystemRollbackResponse(ok=res["ok"], message=res["message"])
