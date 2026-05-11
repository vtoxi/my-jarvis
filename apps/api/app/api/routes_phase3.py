from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.core.automation_state import AutomationState
from app.core.config import settings
from app.core.deps import get_automation, get_hammerspoon
from app.schemas.automation import (
    ActionStepIn,
    ArmRequest,
    ArmResponse,
    ExecuteRequest,
    ExecuteResponse,
    KillResponse,
    NormalizedStepOut,
    PermissionsCheckRequest,
    PermissionsCheckResponse,
    ProfilesListResponse,
    ProfileInfo,
    SystemStatusResponse,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.services.action_log import append_action_log, read_recent_logs
from app.services.execution_runner import run_normalized_steps
from app.services.hammerspoon_service import HammerspoonService
from app.services.permissions_service import RiskTier, evaluate_plan, needs_confirmation
from app.services.workflow_engine import list_profiles, load_profile_resolved

router = APIRouter(tags=["automation"])


def _steps_to_dict(steps: list[ActionStepIn]) -> list[dict]:
    return [s.model_dump() for s in steps]


def _to_out(ns) -> NormalizedStepOut:
    d = asdict(ns)
    d["tier"] = ns.tier.value
    return NormalizedStepOut(**d)


@router.get("/automation/profiles", response_model=ProfilesListResponse)
async def automation_profiles() -> ProfilesListResponse:
    rows = list_profiles()
    return ProfilesListResponse(profiles=[ProfileInfo(**r) for r in rows])


@router.post("/permissions/check", response_model=PermissionsCheckResponse)
async def permissions_check(body: PermissionsCheckRequest) -> PermissionsCheckResponse:
    raw = _steps_to_dict(body.steps)
    normalized, errors = evaluate_plan(raw)
    restricted = any(e for e in errors) or any(n.tier == RiskTier.restricted for n in normalized)
    ok = not restricted and len(errors) == 0
    return PermissionsCheckResponse(
        ok=ok,
        needs_confirmation=needs_confirmation(normalized),
        errors=errors,
        normalized=[_to_out(n) for n in normalized],
    )


@router.post("/workflows/run", response_model=WorkflowRunResponse)
async def workflows_run(
    body: WorkflowRunRequest,
    automation: AutomationState = Depends(get_automation),
    hs: HammerspoonService = Depends(get_hammerspoon),
) -> WorkflowRunResponse:
    if not automation.is_armed():
        return WorkflowRunResponse(ok=False, errors=["automation_disarmed"], message="Use POST /system/arm to re-enable.")

    prof = load_profile_resolved(body.profile_id)
    if not prof:
        raise HTTPException(status_code=404, detail="profile_not_found")
    steps_raw = prof.get("steps") or []
    if not isinstance(steps_raw, list):
        raise HTTPException(status_code=400, detail="invalid_profile")

    normalized, errors = evaluate_plan([x for x in steps_raw if isinstance(x, dict)])
    if errors and any("restricted" in e for e in errors):
        return WorkflowRunResponse(ok=False, errors=errors, preview=[_to_out(n) for n in normalized])
    if any(n.tier == RiskTier.restricted for n in normalized):
        return WorkflowRunResponse(ok=False, errors=["restricted_step_present"], preview=[_to_out(n) for n in normalized])

    need = needs_confirmation(normalized)
    if need and not body.challenge:
        cid = automation.issue_challenge(profile_id=body.profile_id)
        append_action_log(
            settings.data_dir,
            {"event": "workflow_pending_confirm", "session_id": body.session_id, "profile_id": body.profile_id, "challenge": cid},
        )
        return WorkflowRunResponse(
            ok=False,
            pending=True,
            challenge=cid,
            profile_id=body.profile_id,
            message="Confirmation required for one or more steps",
            preview=[_to_out(n) for n in normalized],
        )

    if need and body.challenge:
        if not automation.consume_challenge(body.challenge, body.profile_id):
            raise HTTPException(status_code=400, detail="invalid_or_expired_challenge")

    result = await run_normalized_steps(
        settings=settings,
        automation=automation,
        hs=hs,
        steps=normalized,
        session_id=body.session_id,
        source=f"workflow:{body.profile_id}",
    )
    append_action_log(
        settings.data_dir,
        {"event": "workflow_complete", "session_id": body.session_id, "profile_id": body.profile_id, "result": result},
    )
    return WorkflowRunResponse(
        ok=bool(result.get("ok")),
        results=result.get("results") or [],
        errors=[result["error"]] if result.get("error") else [],
    )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_actions(
    body: ExecuteRequest,
    automation: AutomationState = Depends(get_automation),
    hs: HammerspoonService = Depends(get_hammerspoon),
) -> ExecuteResponse:
    if not automation.is_armed():
        return ExecuteResponse(ok=False, errors=["automation_disarmed"])

    raw = _steps_to_dict(body.steps)
    normalized, errors = evaluate_plan(raw)
    if errors and any("restricted" in e for e in errors):
        return ExecuteResponse(ok=False, errors=errors, preview=[_to_out(n) for n in normalized])
    if any(n.tier == RiskTier.restricted for n in normalized):
        return ExecuteResponse(ok=False, errors=["restricted_step_present"], preview=[_to_out(n) for n in normalized])

    need = needs_confirmation(normalized)
    if need and not body.challenge:
        cid = automation.issue_challenge(profile_id="execute_adhoc")
        return ExecuteResponse(ok=False, pending=True, challenge=cid, preview=[_to_out(n) for n in normalized])
    if need and body.challenge:
        if not automation.consume_challenge(body.challenge, "execute_adhoc"):
            raise HTTPException(status_code=400, detail="invalid_or_expired_challenge")

    result = await run_normalized_steps(
        settings=settings,
        automation=automation,
        hs=hs,
        steps=normalized,
        session_id=body.session_id,
        source="execute",
    )
    return ExecuteResponse(
        ok=bool(result.get("ok")),
        results=result.get("results") or [],
        errors=[result["error"]] if result.get("error") else [],
    )


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status(
    automation: AutomationState = Depends(get_automation),
    hs: HammerspoonService = Depends(get_hammerspoon),
) -> SystemStatusResponse:
    reachable = await hs.health()
    return SystemStatusResponse(
        armed=automation.is_armed(),
        sandbox=settings.automation_sandbox,
        hammerspoon_reachable=reachable,
        last_error=automation.last_error,
        recent_logs=read_recent_logs(settings.data_dir, limit=40),
    )


@router.post("/kill", response_model=KillResponse)
async def kill_switch(automation: AutomationState = Depends(get_automation)) -> KillResponse:
    automation.disarm()
    append_action_log(settings.data_dir, {"event": "kill_switch", "armed": False})
    return KillResponse(armed=False, message="Automation disarmed. Use POST /system/arm to re-enable.")


@router.post("/system/arm", response_model=ArmResponse)
async def system_arm(body: ArmRequest, automation: AutomationState = Depends(get_automation)) -> ArmResponse:
    if body.armed:
        automation.arm()
        automation.set_error(None)
    else:
        automation.disarm()
    append_action_log(settings.data_dir, {"event": "arm_state", "armed": automation.is_armed()})
    return ArmResponse(armed=automation.is_armed())
