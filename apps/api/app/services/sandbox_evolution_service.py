from __future__ import annotations

from typing import Any

from app.services.evolution_store import EvolutionStore


async def list_sandbox_experiments(store: EvolutionStore) -> list[dict[str, Any]]:
    """Surface pending evolution items and recent sandbox-tagged events."""
    events = await store.list_events(limit=40)
    rows: list[dict[str, Any]] = []
    for e in events:
        if e.get("kind") not in ("sandbox", "sandbox_proposed"):
            continue
        p = e.get("payload") or {}
        rows.append(
            {
                "id": str(e.get("id")),
                "kind": "sandbox",
                "status": str(p.get("status") or "recorded"),
                "summary": str(p.get("summary") or e.get("kind")),
                "created_at": str(e.get("created_at")),
            }
        )
    return rows


async def record_sandbox_proposal(store: EvolutionStore, *, summary: str, detail: dict[str, Any]) -> str:
    eid = await store.append_event(kind="sandbox_proposed", payload={"summary": summary, **detail, "status": "proposed"})
    return str(eid)
