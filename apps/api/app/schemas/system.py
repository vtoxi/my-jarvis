from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SubsystemHealth(BaseModel):
    id: str = Field(description="Subsystem identifier")
    ok: bool
    detail: str | None = None
    latency_ms: float | None = None
    optional_for_score: bool = Field(
        default=False,
        description="If true, excluded from aggregate health_score (informational only)",
    )


class SystemHealthResponse(BaseModel):
    status: Literal["ok", "degraded", "critical"] = "ok"
    health_score: int = Field(
        ge=0,
        le=100,
        description="0–100 from subsystems where optional_for_score is false (core stack)",
    )
    subsystems: list[SubsystemHealth] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IncidentRecord(BaseModel):
    id: str
    created_at: str
    severity: str
    subsystem: str | None
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    repair_output: dict[str, Any] | None = None


class SystemErrorsResponse(BaseModel):
    incidents: list[IncidentRecord] = Field(default_factory=list)
    log_tail_hint: str | None = Field(default=None, description="Primary API log file path if configured")


class SystemLogsResponse(BaseModel):
    path: str | None = None
    lines: list[str] = Field(default_factory=list)
    truncated: bool = False


class SystemPerformanceResponse(BaseModel):
    available: bool = False
    cpu_percent: float | None = None
    ram_used_mb: float | None = None
    ram_total_mb: float | None = None
    error: str | None = None
    collected_at_unix: float | None = None


class SystemRepairRequest(BaseModel):
    context: str | None = Field(default=None, max_length=8000, description="Optional operator notes")
    subsystems: list[str] | None = Field(default=None, description="Optional filter; default all")


class SystemRepairResponse(BaseModel):
    incident_id: str
    requires_human_approval: bool = True
    root_cause_hypothesis: str
    severity: str
    user_visible_summary: str
    recommended_commands: list[str] = Field(default_factory=list)
    patch_plan: list[dict[str, Any]] = Field(default_factory=list)
    raw_markdown: str | None = None
    operator_takeover_checklist: list[str] = Field(
        default_factory=list,
        description="Why the operator must act locally (keyboard, logs, screen) — JARVIS does not self-drive the OS",
    )


class SystemAuditRequest(BaseModel):
    mode: Literal["audit", "improve"] = "audit"
    run_tools: bool = Field(default=False, description="If true and env allows, run ruff/mypy/pytest")
    max_tool_output_chars: int = Field(default=24_000, ge=1000, le=200_000)


class SystemAuditResponse(BaseModel):
    audit_id: str
    mode: Literal["audit", "improve"] = "audit"
    tools: dict[str, Any] = Field(default_factory=dict)
    debt_score: int = Field(ge=0, le=100)
    synthesis_markdown: str
    categories: dict[str, list[str]] = Field(
        default_factory=dict,
        description="A–E buckets: stability, performance, architecture, ux, security",
    )
    operator_takeover_checklist: list[str] = Field(
        default_factory=list,
        description="If audit tools were skipped or failed, what the human should do next",
    )


class SystemPatchPrepareRequest(BaseModel):
    diff_text: str = Field(..., max_length=524_288, description="Unified diff to apply after approval")
    branch_suffix: str | None = Field(default=None, max_length=80, description="Optional suffix for git branch name")


class SystemPatchPrepareResponse(BaseModel):
    patch_id: str
    approval_token: str
    expires_at_unix: int
    branch_name: str
    base_sha: str
    diff_sha256: str
    preview_lines: int


class SystemPatchApplyRequest(BaseModel):
    approval_token: str
    diff_text: str = Field(..., max_length=524_288, description="Must match the diff used at prepare (byte-identical)")


class SystemPatchApplyResponse(BaseModel):
    ok: bool
    patch_id: str
    message: str
    pytest_exit_code: int | None = None


class SystemRollbackPrepareRequest(BaseModel):
    patch_id: str


class SystemRollbackPrepareResponse(BaseModel):
    approval_token: str
    expires_at_unix: int
    patch_id: str


class SystemRollbackRequest(BaseModel):
    approval_token: str
    patch_id: str


class SystemRollbackResponse(BaseModel):
    ok: bool
    message: str


class SystemAutoworkStatusResponse(BaseModel):
    enabled: bool
    schedule_enabled: bool
    interval_s: int
    last_run: dict[str, Any] | None = None
    restart_request_path: str | None = None
    restart_pending: bool = False


class SystemAutoworkTickResponse(BaseModel):
    ok: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    event_logged: bool = False
    note: str = Field(
        default="Artifacts under data_dir/autowork/. The API never restarts itself; apply code changes via Phase 6 patch flow with tokens.",
    )
