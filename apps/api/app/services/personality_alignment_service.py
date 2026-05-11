from __future__ import annotations

from typing import Any

from app.schemas.evolution import TwinProfilePayload


def merge_twin_patch(current: dict[str, Any], patch: TwinProfilePayload) -> TwinProfilePayload:
    """Deep-merge top-level twin dimensions; meta merged last."""
    base = {
        "workflow": dict(current.get("workflow") or {}),
        "decision": dict(current.get("decision") or {}),
        "communication": dict(current.get("communication") or {}),
        "focus": dict(current.get("focus") or {}),
        "strategy": dict(current.get("strategy") or {}),
        "meta": dict(current.get("meta") or {}),
    }
    incoming = patch.model_dump()
    for key in ("workflow", "decision", "communication", "focus", "strategy", "meta"):
        if key in incoming and isinstance(incoming[key], dict):
            base[key] = {**base[key], **incoming[key]}
    return TwinProfilePayload.model_validate(base)
