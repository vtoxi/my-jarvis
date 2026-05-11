from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionStepIn(BaseModel):
    type: Literal["open_app", "open_url", "focus", "delay", "tile_preset"]
    target: str = Field(min_length=1, max_length=2048)
    tier: Literal["safe", "confirm", "restricted"] | None = None


class PermissionsCheckRequest(BaseModel):
    steps: list[ActionStepIn]


class NormalizedStepOut(BaseModel):
    type: str
    target: str
    tier: str
    bundle_id: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class PermissionsCheckResponse(BaseModel):
    ok: bool
    needs_confirmation: bool
    errors: list[str] = Field(default_factory=list)
    normalized: list[NormalizedStepOut] = Field(default_factory=list)


class WorkflowRunRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=8, max_length=128)
    challenge: str | None = Field(default=None, description="Approval challenge from pending response")


class WorkflowRunResponse(BaseModel):
    ok: bool
    pending: bool = False
    challenge: str | None = None
    profile_id: str | None = None
    message: str | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    preview: list[NormalizedStepOut] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128)
    steps: list[ActionStepIn]
    challenge: str | None = None
    interpreter_prompt: str | None = Field(default=None, max_length=4000)


class ExecuteResponse(BaseModel):
    ok: bool
    pending: bool = False
    challenge: str | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    preview: list[NormalizedStepOut] = Field(default_factory=list)


class SystemStatusResponse(BaseModel):
    armed: bool
    sandbox: bool
    hammerspoon_reachable: bool
    last_error: str | None
    recent_logs: list[dict[str, Any]]


class KillResponse(BaseModel):
    armed: bool
    message: str


class ArmRequest(BaseModel):
    armed: bool = True


class ArmResponse(BaseModel):
    armed: bool


class ProfileInfo(BaseModel):
    id: str
    label: str
    step_count: int


class ProfilesListResponse(BaseModel):
    profiles: list[ProfileInfo]
