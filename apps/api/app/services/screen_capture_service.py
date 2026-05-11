from __future__ import annotations

import io
import logging

from app.core.config import Settings

logger = logging.getLogger(__name__)


def capture_primary_monitor_png(*, max_width: int) -> tuple[bytes, int, int]:
    """Capture primary display as PNG bytes. Requires Screen Recording permission on macOS."""
    try:
        import mss  # type: ignore[import-untyped]
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("mss and Pillow are required for screen capture") from e

    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        pil = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        w, h = pil.size
        if max_width and w > max_width:
            ratio = max_width / float(w)
            pil = pil.resize((max_width, max(1, int(h * ratio))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        pil.save(buf, format="PNG", optimize=True)
        out = buf.getvalue()
        return out, pil.size[0], pil.size[1]


def capture_stub(*, max_width: int) -> tuple[bytes, int, int]:
    """1×1 transparent PNG for private mode / tests."""
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Pillow required") from e
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), 1, 1


def capture_for_pipeline(settings: Settings, *, private_mode: bool) -> tuple[bytes, int, int, str | None]:
    if private_mode:
        b, w, h = capture_stub(max_width=settings.screen_max_capture_width)
        return b, w, h, "private_mode_stub"
    try:
        b, w, h = capture_primary_monitor_png(max_width=int(settings.screen_max_capture_width))
        return b, w, h, None
    except Exception as e:
        logger.warning("screen capture failed: %s", e)
        raise
