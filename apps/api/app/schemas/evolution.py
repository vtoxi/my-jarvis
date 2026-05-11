from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TwinProfilePayload(BaseModel):
    """Editable executive-twin dimensions (local JSON; never impersonation)."""

    workflow: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    communication: dict[str, Any] = Field(default_factory=dict)
    focus: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="confidence_by_dimension, notes, last_corrected_at",
    )


class EvolutionStatusResponse(BaseModel):
    twin_version: int
    twin_confidence: dict[str, float] = Field(default_factory=dict)
    last_idle_run_at: str | None = None
    last_idle_run_id: str | None = None
    pending_approvals: int = 0
    evolution_events_24h: int = 0
    strategic_maturity_index: int = Field(ge=0, le=100, description="Heuristic from twin completeness + idle runs")
    self_healing_hint: str | None = Field(default=None, description="Pointer to GET /system/health")
    ethics_note: str = Field(
        default="Style alignment only — no external identity delegation. All learning is logged locally.",
    )
    idle_schedule_enabled: bool = Field(
        default=False,
        description="True when API background loop will run idle learning on an interval",
    )
    idle_schedule_interval_s: int | None = Field(
        default=None,
        description="Interval in seconds when schedule is enabled; null when schedule off",
    )
    knowledge_enabled: bool = Field(default=True, description="Local KG + embeddings feature gate")
    knowledge_chunk_count: int = Field(default=0, ge=0, description="Rows in kg_chunks table")


class EvolutionIdleResponse(BaseModel):
    run_id: str
    report_markdown: str
    actions_proposed: list[str] = Field(default_factory=list)
    requires_approval: bool = True


class EvolutionSandboxItem(BaseModel):
    id: str
    kind: str
    status: str
    summary: str
    created_at: str


class EvolutionSandboxResponse(BaseModel):
    experiments: list[EvolutionSandboxItem] = Field(default_factory=list)
    note: str = Field(
        default="Git-backed experiments use Phase 6 /system/improve/* and /system/patch/queue.",
    )


class EvolutionSandboxPostBody(BaseModel):
    summary: str = Field(default="sandbox experiment", max_length=2000)
    detail: dict[str, Any] = Field(default_factory=dict)


class EvolutionLearnRequest(BaseModel):
    source: Literal["slack", "command", "correction", "local_doc", "manual"] = "manual"
    summary: str = Field(..., max_length=2000)
    detail: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    index_knowledge: bool = Field(
        default=False,
        description="If true and knowledge is enabled, embed summary into local kg_chunks (same privacy as learn log)",
    )


class EvolutionLearnResponse(BaseModel):
    event_id: str
    pending_id: str | None = None
    approval_token: str | None = None
    expires_at_unix: int | None = None


class EvolutionApproveRequest(BaseModel):
    approval_token: str
    pending_id: str


class EvolutionApproveResponse(BaseModel):
    ok: bool
    message: str


class EvolutionTwinResponse(BaseModel):
    version: int
    profile: TwinProfilePayload
    updated_at: str | None = None


class EvolutionTwinPatchRequest(BaseModel):
    profile: TwinProfilePayload
    correction_note: str | None = Field(default=None, max_length=4000)


class EvolutionRollbackRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=20, description="Twin version steps to roll back")


class EvolutionRollbackResponse(BaseModel):
    ok: bool
    version: int
    message: str


class EvolutionLogEntry(BaseModel):
    id: int
    created_at: str
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EvolutionLogsResponse(BaseModel):
    entries: list[EvolutionLogEntry] = Field(default_factory=list)


class EvolutionKnowledgeIngestRequest(BaseModel):
    source: str = Field(default="manual", max_length=200)
    text: str = Field(..., max_length=24_000)
    meta: dict[str, Any] = Field(default_factory=dict)


class EvolutionKnowledgeIngestResponse(BaseModel):
    chunk_id: str


class EvolutionKnowledgeStatusResponse(BaseModel):
    enabled: bool
    chunk_count: int
    last_created_at: str | None = None


class EvolutionKnowledgeHit(BaseModel):
    id: str
    created_at: str
    source: str
    text: str
    score: float
    meta: dict[str, Any] = Field(default_factory=dict)


class EvolutionKnowledgeSearchResponse(BaseModel):
    query: str
    hits: list[EvolutionKnowledgeHit] = Field(default_factory=list)


class EvolutionSandboxBenchmarkResponse(BaseModel):
    ok: bool
    skipped: bool = False
    reason: str | None = None
    repo_root: str | None = None
    summary: dict[str, Any] | None = None
    note: str = Field(
        default="Uses Phase 6 tooling: set JARVIS_REPO_ROOT and JARVIS_SYSTEM_ALLOW_SUBPROCESS=true.",
    )
