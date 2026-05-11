from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SlackOAuthCallbackQuery(BaseModel):
    code: str | None = None
    state: str | None = None
    error: str | None = None


class SlackDraftRequest(BaseModel):
    """Draft-only (Phase 4B). Never sends to Slack."""

    channel_id: str = Field(..., min_length=1)
    thread_ts: str | None = None
    context: str = Field(..., min_length=1, description="Thread or situation summary for drafting")
    tone: Literal["executive", "friendly", "technical"] = "executive"
    model: str | None = Field(default=None, description="Ollama model id; defaults to server default")


class SlackBriefingRequest(BaseModel):
    max_channels: int = Field(default=8, ge=1, le=30)
    messages_per_channel: int = Field(default=40, ge=5, le=200)
    model: str | None = Field(default=None, description="Ollama model id (e.g. llama3); defaults to server default")


class SlackChannelPrefs(BaseModel):
    priority_channel_ids: list[str] = Field(default_factory=list)
    priority_keywords: list[str] = Field(
        default_factory=lambda: ["urgent", "asap", "blocker", "deadline", "today", "eod"]
    )
    vip_user_ids: list[str] = Field(default_factory=list)


class SlackSendPrepareRequest(BaseModel):
    """Step 1 of 4C: mint a short-lived signed token for an exact message body."""

    channel_id: str = Field(..., min_length=1)
    thread_ts: str | None = Field(default=None, description="Reply in thread (parent message ts)")
    text: str = Field(..., min_length=1, max_length=12000, description="Exact text that will be sent if you confirm")


class SlackSendConfirmRequest(BaseModel):
    """Step 2 of 4C: send only if token matches channel, thread, and text hash."""

    approval_token: str = Field(..., min_length=8)
    text: str = Field(..., min_length=1, max_length=12000, description="Must match the text used when preparing the token")
