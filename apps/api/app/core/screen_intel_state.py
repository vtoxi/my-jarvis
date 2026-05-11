from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

AssistMode = Literal["passive", "advisory", "interactive", "controlled"]


@dataclass
class ScreenIntelState:
    """In-memory operator controls + last snapshot (no raw image retained by default)."""

    monitoring_paused: bool = False
    private_mode: bool = False
    assist_mode: AssistMode = "advisory"
    excluded_app_substrings: list[str] = field(
        default_factory=lambda: ["1Password", "Keychain", "loginwindow", "Screen Sharing"]
    )
    capture_interval_s: float = 45.0
    last_front_app: str | None = None
    last_window_title: str | None = None
    last_ocr_excerpt: str = ""
    last_context_tags: list[str] = field(default_factory=list)
    last_capture_mono: float = 0.0
    last_capture_error: str | None = None
    last_width: int | None = None
    last_height: int | None = None
    last_productivity_score: int | None = None
    focus_running: bool = False
    focus_started_mono: float | None = None

    def app_excluded(self, front_app: str | None) -> bool:
        if not front_app:
            return False
        low = front_app.lower()
        for frag in self.excluded_app_substrings:
            if frag.lower() in low:
                return True
        return False

    def touch_focus_tick(self) -> None:
        if self.focus_running and self.focus_started_mono is None:
            self.focus_started_mono = time.monotonic()

    def focus_elapsed_seconds(self) -> int:
        if not self.focus_running or self.focus_started_mono is None:
            return 0
        return max(0, int(time.monotonic() - self.focus_started_mono))

    def focus_start(self) -> None:
        self.focus_running = True
        self.focus_started_mono = time.monotonic()

    def focus_stop(self) -> None:
        self.focus_running = False
        self.focus_started_mono = None
