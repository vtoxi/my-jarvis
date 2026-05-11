from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def _run_osascript(script: str, timeout: float = 4.0) -> str | None:
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if r.returncode != 0:
            return None
        out = (r.stdout or "").strip()
        return out or None
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.debug("osascript failed: %s", e)
        return None


def frontmost_app_darwin() -> str | None:
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    return _run_osascript(script)


def front_window_title_darwin() -> str | None:
    script = (
        'tell application "System Events" to tell (first process whose frontmost is true) '
        'to if exists window 1 then get title of window 1 else return ""'
    )
    return _run_osascript(script)


def detect_front_context() -> dict[str, Any]:
    """Best-effort active app + window title. Non-macOS returns placeholders."""
    if platform.system() != "Darwin":
        return {"front_app": None, "window_title": None, "platform": platform.system()}

    app = frontmost_app_darwin()
    title = front_window_title_darwin()
    return {"front_app": app, "window_title": title, "platform": "Darwin"}


def infer_context_tags(front_app: str | None, window_title: str | None, ocr_snippet: str) -> list[str]:
    tags: list[str] = []
    fa = (front_app or "").lower()
    wt = (window_title or "").lower()
    oc = (ocr_snippet or "").lower()

    if "slack" in fa or "slack" in wt:
        tags.append("messaging_slack")
    if "cursor" in fa or "cursor" in wt:
        tags.append("ide_cursor")
    if "visual studio" in fa or "vscode" in fa:
        tags.append("ide_vscode")
    if "terminal" in fa or "iterm" in fa or "ghostty" in fa or "kitty" in fa:
        tags.append("terminal")
    if any(b in fa for b in ("chrome", "safari", "firefox", "arc", "brave", "edge")):
        tags.append("browser")
    if "jira" in wt or "jira" in oc:
        tags.append("jira")
    if "notion" in fa or "notion" in wt:
        tags.append("notion")
    if "mail" in fa or "outlook" in fa:
        tags.append("email")
    if "zoom" in fa or "meet" in fa or "teams" in fa:
        tags.append("meeting")
    if "github" in wt or "github" in oc:
        tags.append("github")
    if not tags:
        tags.append("general")
    return sorted(set(tags))
