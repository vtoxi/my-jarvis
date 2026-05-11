from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import anyio
from starlette.applications import Starlette

from app.core.config import Settings
from app.services.diagnostics_service import gather_system_health
from app.services.evolution_embeddings import embed_for_knowledge
from app.services.evolution_store import EvolutionStore
from app.services.idle_learning_crew_runner import run_idle_learning_crew

logger = logging.getLogger(__name__)


def _tail_api_log(log_path: Path | None, *, max_lines: int = 80) -> str:
    if log_path is None or not log_path.is_file():
        return "(no api log file yet)"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(log read error)"
    return "\n".join(lines[-max_lines:])


async def run_idle_cycle(
    *,
    app: Starlette,
    settings: Settings,
    store: EvolutionStore,
) -> tuple[str, str, list[str], dict[str, Any]]:
    if not settings.evolution_idle_enabled:
        raise ValueError("JARVIS_EVOLUTION_IDLE_ENABLED is false — idle learning disabled")

    health = await gather_system_health(app, settings)
    health_json = health.model_dump_json()
    log_path = getattr(app.state, "api_log_path", None)
    log_tail = _tail_api_log(log_path if isinstance(log_path, Path) else None)
    _v, twin_payload, _ = await store.get_twin()
    twin_json = json.dumps(twin_payload, indent=2)[:12000]

    knowledge_digest = ""
    kg_hits_n = 0
    if settings.evolution_knowledge_enabled:
        try:
            ollama = getattr(app.state, "ollama", None)
            q = "Operator workflow preferences, recurring tasks, blockers, and priorities."
            q_emb = await embed_for_knowledge(settings, ollama, q)
            hits = await store.kg_search(
                q_emb,
                top_k=4,
                max_rows=settings.evolution_knowledge_search_max_rows,
            )
            kg_hits_n = len(hits)
            if hits:
                lines = [f"- ({h['source']}) {h['text'][:500]}" for h in hits]
                knowledge_digest = "Top local knowledge chunks (cosine similarity):\n" + "\n".join(lines)
        except Exception as e:  # noqa: BLE001
            logger.warning("knowledge digest for idle skipped: %s", e)

    result = await anyio.to_thread.run_sync(
        lambda: run_idle_learning_crew(
            settings=settings,
            health_json=health_json,
            log_tail=log_tail,
            twin_json=twin_json,
            model=settings.default_ollama_model,
            knowledge_digest=knowledge_digest,
        )
    )
    metrics = {
        "health_score": health.health_score,
        "health_status": health.status,
        "actions_count": len(result.actions_proposed),
        "knowledge_hits_in_context": kg_hits_n,
    }
    rid = await store.append_idle_run(report=result.report_markdown, metrics=metrics)
    await store.append_event(
        kind="idle_complete",
        payload={"run_id": rid, "actions": result.actions_proposed[:20]},
    )
    logger.info("idle learning cycle complete run_id=%s", rid)
    return rid, result.report_markdown, result.actions_proposed, metrics
