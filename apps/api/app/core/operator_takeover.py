"""Copy for when automation cannot safely fix a problem — human-in-the-loop by design."""

from __future__ import annotations

from typing import Final

# Intentionally generic: no secrets, no URLs that assume a host.
OPERATOR_TAKEOVER_LINES: Final[tuple[str, ...]] = (
    "JARVIS does not auto-run shell commands, move your mouse, or type into other apps — that avoids silent damage and "
    "respects macOS privacy.",
    "If diagnosis is incomplete, use Copilot / screen flows: POST /screen/capture or GET /screen/context, then paste "
    "relevant OCR or notes into POST /system/repair `context`.",
    "Use GET /system/logs (or the log path shown in errors) while you reproduce the issue in Terminal or the failing app.",
    "UI automation exists only where you enable it (Control deck + Hammerspoon bridge + explicit approvals) — not from "
    "background repair jobs.",
    "For code fixes, use the signed patch rail (POST /system/improve/prepare → apply with token) after you review the diff.",
)


def operator_takeover_lines(*, extra: str | None = None) -> list[str]:
    out = list(OPERATOR_TAKEOVER_LINES)
    if extra and extra.strip():
        out.append(extra.strip()[:2000])
    return out
