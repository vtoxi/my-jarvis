from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class AutomationState:
    armed: bool = True
    last_error: str | None = None
    _challenges: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def disarm(self) -> None:
        with self._lock:
            self.armed = False

    def arm(self) -> None:
        with self._lock:
            self.armed = True

    def is_armed(self) -> bool:
        with self._lock:
            return self.armed

    def set_error(self, msg: str | None) -> None:
        with self._lock:
            self.last_error = msg

    def issue_challenge(self, *, profile_id: str, ttl_s: int = 120) -> str:
        cid = secrets.token_urlsafe(16)
        with self._lock:
            self._challenges[cid] = {"profile_id": profile_id, "exp": time.time() + ttl_s}
        return cid

    def consume_challenge(self, challenge_id: str, profile_id: str) -> bool:
        now = time.time()
        with self._lock:
            row = self._challenges.pop(challenge_id, None)
            if not row:
                return False
            if row.get("profile_id") != profile_id:
                return False
            if float(row.get("exp", 0)) < now:
                return False
        return True
