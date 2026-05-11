from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _log_path(data_dir: Path) -> Path:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "actions.log"


def append_action_log(data_dir: Path, record: dict[str, Any]) -> None:
    path = _log_path(data_dir)
    line = json.dumps({**record, "ts": datetime.now(UTC).isoformat()}, ensure_ascii=False)
    try:
        with _lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError as exc:
        logger.warning("action log write failed: %s", exc)


def read_recent_logs(data_dir: Path, limit: int = 40) -> list[dict[str, Any]]:
    path = _log_path(data_dir)
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
