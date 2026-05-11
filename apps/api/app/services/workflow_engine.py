from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def profiles_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "automation" / "profiles"


def list_profiles() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    d = profiles_dir()
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                out.append(
                    {
                        "id": data["id"],
                        "label": data.get("label", data["id"]),
                        "step_count": len(data.get("steps", []) or []),
                    },
                )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("skip profile %s: %s", p, exc)
    return out


def load_profile(profile_id: str) -> dict[str, Any] | None:
    path = profiles_dir() / f"{profile_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def load_profile_resolved(profile_id: str) -> dict[str, Any] | None:
    return load_profile(profile_id)
