from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssistMode = Literal["passive", "advisory", "interactive", "controlled"]


class ScreenCaptureRequest(BaseModel):
    include_image: bool = Field(default=False, description="Return base64 PNG (large); off by default for privacy")
    force: bool = Field(default=False, description="Run even if within passive interval hint")


class ScreenOcrRequest(BaseModel):
    image_base64: str = Field(..., min_length=8, description="PNG/JPEG base64 payload")


class CopilotConfigBody(BaseModel):
    monitoring_paused: bool | None = None
    private_mode: bool | None = None
    assist_mode: AssistMode | None = None
    excluded_app_substrings: list[str] | None = None
    capture_interval_s: float | None = Field(default=None, ge=5.0, le=600.0)


class CopilotSuggestionsRequest(BaseModel):
    model: str | None = None
    refresh_screen: bool = Field(default=False, description="Run capture+OCR before crew")


class FocusControlBody(BaseModel):
    action: Literal["start", "stop", "reset"]
