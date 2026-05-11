from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SiblingProjectId = Literal["open_interpreter", "crewai"]


class SiblingProjectStartBody(BaseModel):
    """Optional override for one-off starts (advanced)."""

    cmd: str | None = Field(default=None, description="If set, replaces configured start command for this request only")


class SiblingPathsResponse(BaseModel):
    sibling_workspace_parent: str
    open_interpreter_dir: str
    crewai_dir: str
