from __future__ import annotations

import base64
import logging
import time
from typing import Any

from app.core.config import Settings
from app.core.screen_intel_state import ScreenIntelState
from app.memory.context_history_store import ContextHistoryStore
from app.services.app_context_service import detect_front_context, infer_context_tags
from app.services.ocr_service import ocr_png_bytes, ocr_stub
from app.services.screen_capture_service import capture_for_pipeline

logger = logging.getLogger(__name__)


def _productivity_score(tags: list[str], ocr: str) -> int:
    score = 72
    low = ocr.lower()
    if "error" in low or "traceback" in low or "exception" in low:
        score -= 12
    if "urgent" in low or "asap" in low or "blocker" in low:
        score -= 10
    if "messaging_slack" in tags:
        score -= 4
    if "meeting" in tags:
        score -= 6
    if "ide_" in "".join(tags):
        score += 4
    return max(35, min(98, score))


async def run_snapshot(
    *,
    settings: Settings,
    state: ScreenIntelState,
    history: ContextHistoryStore | None,
    include_image: bool,
) -> dict[str, Any]:
    mono = time.monotonic()
    ctx = detect_front_context()
    front = ctx.get("front_app")
    title = ctx.get("window_title")

    state.last_front_app = front
    state.last_window_title = title

    if state.monitoring_paused:
        state.last_capture_error = "monitoring_paused"
        state.last_ocr_excerpt = ""
        state.last_context_tags = []
        state.last_productivity_score = None
        state.last_capture_mono = mono
        return {
            "ok": False,
            "reason": "monitoring_paused",
            "front_app": front,
            "window_title": title,
            "include_image": False,
        }

    if state.app_excluded(front):
        state.last_capture_error = "app_excluded"
        state.last_ocr_excerpt = ""
        state.last_context_tags = infer_context_tags(front, title, "")
        state.last_productivity_score = _productivity_score(state.last_context_tags, "")
        state.last_capture_mono = mono
        return {
            "ok": True,
            "skipped_capture": True,
            "reason": "app_excluded",
            "front_app": front,
            "window_title": title,
            "tags": state.last_context_tags,
            "include_image": False,
        }

    if not settings.screen_intel_enabled:
        state.last_capture_error = "screen_intel_disabled"
        return {"ok": False, "reason": "screen_intel_disabled"}

    try:
        png, w, h, cap_note = capture_for_pipeline(settings, private_mode=state.private_mode)
    except Exception as e:
        state.last_capture_error = str(e)
        logger.warning("capture pipeline: %s", e)
        return {"ok": False, "reason": "capture_failed", "detail": str(e), "front_app": front, "window_title": title}

    if cap_note == "private_mode_stub":
        text, ocr_err = ocr_stub(png)
    else:
        text, ocr_err = ocr_png_bytes(png)

    excerpt = (text or "")[:12000]
    tags = infer_context_tags(front, title, excerpt)
    state.last_ocr_excerpt = excerpt
    state.last_context_tags = tags
    state.last_width = w
    state.last_height = h
    state.last_capture_error = ocr_err
    state.last_capture_mono = mono
    state.last_productivity_score = _productivity_score(tags, excerpt)

    if history is not None:
        try:
            await history.append_snapshot(
                front_app=front,
                window_title=title,
                ocr_excerpt=excerpt,
                tags=tags,
            )
        except Exception as e:
            logger.warning("context history append failed: %s", e)

    out: dict[str, Any] = {
        "ok": True,
        "front_app": front,
        "window_title": title,
        "ocr_char_count": len(excerpt),
        "ocr_error": ocr_err,
        "tags": tags,
        "width": w,
        "height": h,
        "productivity_score": _productivity_score(tags, excerpt),
        "include_image": bool(include_image),
    }
    if include_image and not state.private_mode:
        out["image_base64"] = base64.b64encode(png).decode("ascii")
    else:
        out["image_base64"] = None
    return out


def build_evidence_block(state: ScreenIntelState) -> str:
    lines = [
        f"Front app: {state.last_front_app or 'unknown'}",
        f"Window title: {state.last_window_title or 'unknown'}",
        f"Tags: {', '.join(state.last_context_tags) or 'none'}",
        "",
        "### OCR excerpt",
        (state.last_ocr_excerpt or "(empty)")[:10000],
    ]
    return "\n".join(lines)
