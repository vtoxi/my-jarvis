from __future__ import annotations

import base64
import logging
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.screen_intel_state import ScreenIntelState
from app.schemas.phase5 import (
    CopilotConfigBody,
    CopilotSuggestionsRequest,
    FocusControlBody,
    ScreenCaptureRequest,
    ScreenOcrRequest,
)
from app.services.ocr_service import ocr_png_bytes
from app.services.screen_crew_runner import run_screen_intel_crew
from app.services.screen_intel_pipeline import build_evidence_block, run_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["screen", "copilot", "focus"])


def _intel(request: Request) -> ScreenIntelState:
    return request.app.state.screen_intel


def _history(request: Request) -> Any:
    return getattr(request.app.state, "context_history", None)


@router.post("/screen/capture")
async def screen_capture(request: Request, body: ScreenCaptureRequest) -> dict[str, Any]:
    hist = _history(request)
    try:
        return await run_snapshot(
            settings=settings,
            state=_intel(request),
            history=hist,
            include_image=body.include_image,
        )
    except Exception as e:
        logger.exception("screen capture")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/screen/context")
async def screen_context(request: Request, refresh: bool = False) -> dict[str, Any]:
    st = _intel(request)
    if refresh:
        hist = _history(request)
        await run_snapshot(settings=settings, state=st, history=hist, include_image=False)
    return {
        "front_app": st.last_front_app,
        "window_title": st.last_window_title,
        "tags": st.last_context_tags,
        "ocr_excerpt": (st.last_ocr_excerpt or "")[:4000],
        "ocr_excerpt_truncated": len(st.last_ocr_excerpt or "") > 4000,
        "last_capture_mono": st.last_capture_mono,
        "last_error": st.last_capture_error,
        "width": st.last_width,
        "height": st.last_height,
        "monitoring_paused": st.monitoring_paused,
        "private_mode": st.private_mode,
        "assist_mode": st.assist_mode,
        "visible_indicator": True,
        "trust_note": "JARVIS reads the screen only when you refresh or run capture — no silent cloud upload.",
        "productivity_score": st.last_productivity_score,
    }


@router.post("/screen/ocr")
async def screen_ocr(body: ScreenOcrRequest) -> dict[str, Any]:
    def work() -> tuple[str, str | None]:
        raw = base64.b64decode(body.image_base64, validate=True)
        return ocr_png_bytes(raw)

    try:
        text, err = await anyio.to_thread.run_sync(work)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid_image:{e}") from e
    return {"text": text, "error": err, "char_count": len(text or "")}


@router.get("/copilot/status")
async def copilot_status(request: Request) -> dict[str, Any]:
    st = _intel(request)
    hist = _history(request)
    recent: list[dict[str, Any]] = []
    if hist is not None:
        try:
            recent = await hist.recent_plain(limit=8)
        except Exception as e:
            logger.debug("recent context: %s", e)
    return {
        "monitoring_paused": st.monitoring_paused,
        "private_mode": st.private_mode,
        "assist_mode": st.assist_mode,
        "excluded_app_substrings": st.excluded_app_substrings,
        "capture_interval_s": st.capture_interval_s,
        "screen_intel_enabled": settings.screen_intel_enabled,
        "last_front_app": st.last_front_app,
        "last_tags": st.last_context_tags,
        "last_capture_mono": st.last_capture_mono,
        "recent_snapshots": recent,
    }


@router.post("/copilot/config")
async def copilot_config(request: Request, body: CopilotConfigBody) -> dict[str, Any]:
    st = _intel(request)
    if body.monitoring_paused is not None:
        st.monitoring_paused = body.monitoring_paused
    if body.private_mode is not None:
        st.private_mode = body.private_mode
    if body.assist_mode is not None:
        st.assist_mode = body.assist_mode
    if body.excluded_app_substrings is not None:
        st.excluded_app_substrings = [x.strip() for x in body.excluded_app_substrings if x.strip()]
    if body.capture_interval_s is not None:
        st.capture_interval_s = float(body.capture_interval_s)
    return {"ok": True, "applied": body.model_dump(exclude_unset=True)}


@router.post("/copilot/suggestions")
async def copilot_suggestions(request: Request, body: CopilotSuggestionsRequest) -> dict[str, Any]:
    st = _intel(request)
    hist = _history(request)
    if body.refresh_screen:
        await run_snapshot(settings=settings, state=st, history=hist, include_image=False)

    evidence = build_evidence_block(st)
    model = (body.model or settings.default_ollama_model).strip()

    def work():
        return run_screen_intel_crew(
            settings=settings,
            evidence_block=evidence,
            assist_mode=st.assist_mode,
            model=model,
        )

    try:
        crew = await anyio.to_thread.run_sync(work)
    except Exception as e:
        logger.exception("copilot suggestions")
        raise HTTPException(status_code=502, detail=str(e)) from e

    combined = crew.context_markdown.rstrip() + "\n\n---\n\n" + crew.copilot_markdown.strip()
    return {
        "markdown": combined,
        "context": crew.context_markdown,
        "copilot": crew.copilot_markdown,
        "assist_mode": st.assist_mode,
        "model": model,
    }


@router.get("/focus/state")
async def focus_state(request: Request) -> dict[str, Any]:
    st = _intel(request)
    return {
        "running": st.focus_running,
        "elapsed_seconds": st.focus_elapsed_seconds(),
        "assist_mode": st.assist_mode,
    }


@router.post("/focus/control")
async def focus_control(request: Request, body: FocusControlBody) -> dict[str, Any]:
    st = _intel(request)
    if body.action == "start":
        st.focus_start()
    elif body.action == "stop":
        st.focus_stop()
    else:
        st.focus_stop()
        st.focus_start()
    return {"ok": True, "action": body.action, "elapsed_seconds": st.focus_elapsed_seconds()}
