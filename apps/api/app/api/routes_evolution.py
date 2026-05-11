from __future__ import annotations

import logging
import time

import anyio
from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.schemas.evolution import (
    EvolutionApproveRequest,
    EvolutionApproveResponse,
    EvolutionIdleResponse,
    EvolutionKnowledgeHit,
    EvolutionKnowledgeIngestRequest,
    EvolutionKnowledgeIngestResponse,
    EvolutionKnowledgeSearchResponse,
    EvolutionKnowledgeStatusResponse,
    EvolutionLearnRequest,
    EvolutionLearnResponse,
    EvolutionLogsResponse,
    EvolutionRollbackRequest,
    EvolutionRollbackResponse,
    EvolutionSandboxBenchmarkResponse,
    EvolutionSandboxPostBody,
    EvolutionSandboxResponse,
    EvolutionSandboxItem,
    EvolutionStatusResponse,
    EvolutionTwinPatchRequest,
    EvolutionTwinResponse,
    EvolutionLogEntry,
    TwinProfilePayload,
)
from app.services.evolution_approval import mint_learn_approval_token, verify_learn_approval_token
from app.services.evolution_embeddings import embed_for_knowledge
from app.services.evolution_store import EvolutionStore
from app.services.idle_learning_service import run_idle_cycle
from app.services.personality_alignment_service import merge_twin_patch
from app.services.predictive_diagnostics import build_predictions, strategic_maturity_index
from app.services.sandbox_bench_service import compact_benchmark_for_event, run_sandbox_benchmark
from app.services.sandbox_evolution_service import list_sandbox_experiments, record_sandbox_proposal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evolution", tags=["evolution", "phase8"])


def _store(request: Request) -> EvolutionStore:
    st = getattr(request.app.state, "evolution", None)
    if st is None:
        raise HTTPException(status_code=503, detail="Evolution store not initialized")
    return st


@router.get("/status", response_model=EvolutionStatusResponse)
async def evolution_status(request: Request) -> EvolutionStatusResponse:
    store = _store(request)
    ver, twin, _ = await store.get_twin()
    last_id, last_at = await store.last_idle_run()
    pending = await store.count_pending()
    ev24 = await store.count_events_since(24)
    meta = twin.get("meta") or {}
    conf = meta.get("confidence_by_dimension") or {}
    conf_f = {str(k): float(v) for k, v in conf.items() if isinstance(v, (int, float))}
    idle_n = await store.count_idle_runs()
    smi = strategic_maturity_index(twin_payload=twin, idle_run_count=idle_n)
    sched_on = bool(settings.evolution_idle_schedule_enabled and settings.evolution_idle_enabled)
    kg_n = await store.kg_count()
    return EvolutionStatusResponse(
        twin_version=ver,
        twin_confidence=conf_f,
        last_idle_run_at=last_at,
        last_idle_run_id=last_id,
        pending_approvals=pending,
        evolution_events_24h=ev24,
        strategic_maturity_index=smi,
        self_healing_hint="GET /system/health for subsystem matrix; POST /system/repair for diagnosis narrative",
        idle_schedule_enabled=sched_on,
        idle_schedule_interval_s=(settings.evolution_idle_schedule_interval_s if sched_on else None),
        knowledge_enabled=bool(settings.evolution_knowledge_enabled),
        knowledge_chunk_count=kg_n,
    )


@router.post("/idle", response_model=EvolutionIdleResponse)
async def evolution_idle(request: Request) -> EvolutionIdleResponse:
    store = _store(request)
    try:
        rid, report, actions, _metrics = await run_idle_cycle(app=request.app, settings=settings, store=store)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except Exception as e:
        logger.exception("idle cycle")
        raise HTTPException(status_code=502, detail=str(e)) from e
    return EvolutionIdleResponse(run_id=rid, report_markdown=report, actions_proposed=actions, requires_approval=True)


@router.get("/sandbox", response_model=EvolutionSandboxResponse)
async def evolution_sandbox_get(request: Request) -> EvolutionSandboxResponse:
    store = _store(request)
    experiments = await list_sandbox_experiments(store)
    items = [
        EvolutionSandboxItem(
            id=str(x["id"]),
            kind=str(x.get("kind") or "sandbox"),
            status=str(x.get("status") or "unknown"),
            summary=str(x.get("summary") or ""),
            created_at=str(x.get("created_at") or ""),
        )
        for x in experiments
    ]
    pend = await store.list_pending(limit=20)
    for p in pend:
        if p.get("kind") == "sandbox":
            items.append(
                EvolutionSandboxItem(
                    id=str(p["id"]),
                    kind="sandbox_pending",
                    status="pending",
                    summary=str((p.get("payload") or {}).get("summary") or p["kind"]),
                    created_at=str(p["created_at"]),
                )
            )
    return EvolutionSandboxResponse(experiments=items)


@router.post("/sandbox")
async def evolution_sandbox_post(request: Request, body: EvolutionSandboxPostBody) -> dict[str, object]:
    store = _store(request)
    summary = body.summary.strip() or "sandbox experiment"
    detail = dict(body.detail)
    eid = await record_sandbox_proposal(store, summary=summary, detail=detail)
    pid = await store.insert_pending(kind="sandbox", payload={"summary": summary, "detail": detail, "event_id": eid})
    return {"ok": True, "event_id": eid, "pending_id": pid}


@router.post("/sandbox/benchmark", response_model=EvolutionSandboxBenchmarkResponse)
async def evolution_sandbox_benchmark(request: Request) -> EvolutionSandboxBenchmarkResponse:
    store = _store(request)
    try:
        res = await anyio.to_thread.run_sync(lambda: run_sandbox_benchmark(settings))
    except Exception as e:
        logger.exception("sandbox benchmark")
        raise HTTPException(status_code=502, detail=str(e)) from e
    await store.append_event(kind="sandbox_benchmark", payload=compact_benchmark_for_event(res))
    if res.get("skipped"):
        return EvolutionSandboxBenchmarkResponse(
            ok=False,
            skipped=True,
            reason=str(res.get("reason") or "skipped"),
            repo_root=None,
            summary=None,
        )
    return EvolutionSandboxBenchmarkResponse(
        ok=bool(res.get("ok")),
        skipped=False,
        reason=None,
        repo_root=str(res.get("repo_root") or ""),
        summary=res.get("summary") if isinstance(res.get("summary"), dict) else None,
    )


@router.get("/knowledge/status", response_model=EvolutionKnowledgeStatusResponse)
async def evolution_knowledge_status(request: Request) -> EvolutionKnowledgeStatusResponse:
    store = _store(request)
    if not settings.evolution_knowledge_enabled:
        raise HTTPException(status_code=403, detail="JARVIS_EVOLUTION_KNOWLEDGE_ENABLED=false")
    last = await store.kg_last_created()
    n = await store.kg_count()
    return EvolutionKnowledgeStatusResponse(enabled=True, chunk_count=n, last_created_at=last)


@router.post("/knowledge/ingest", response_model=EvolutionKnowledgeIngestResponse)
async def evolution_knowledge_ingest(request: Request, body: EvolutionKnowledgeIngestRequest) -> EvolutionKnowledgeIngestResponse:
    store = _store(request)
    if not settings.evolution_knowledge_enabled:
        raise HTTPException(status_code=403, detail="JARVIS_EVOLUTION_KNOWLEDGE_ENABLED=false")
    ollama = getattr(request.app.state, "ollama", None)
    emb = await embed_for_knowledge(settings, ollama, body.text.strip())
    cid = await store.kg_insert(
        source=body.source.strip() or "manual",
        text=body.text.strip(),
        embedding=emb,
        meta=body.meta,
    )
    await store.append_event(kind="kg_ingest", payload={"chunk_id": cid, "source": body.source})
    return EvolutionKnowledgeIngestResponse(chunk_id=cid)


@router.get("/knowledge/search", response_model=EvolutionKnowledgeSearchResponse)
async def evolution_knowledge_search(
    request: Request,
    q: str,
    top_k: int = 8,
) -> EvolutionKnowledgeSearchResponse:
    store = _store(request)
    if not settings.evolution_knowledge_enabled:
        raise HTTPException(status_code=403, detail="JARVIS_EVOLUTION_KNOWLEDGE_ENABLED=false")
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query q is required")
    if len(query) > 4000:
        raise HTTPException(status_code=400, detail="query too long")
    ollama = getattr(request.app.state, "ollama", None)
    q_emb = await embed_for_knowledge(settings, ollama, query)
    rows = await store.kg_search(
        q_emb,
        top_k=max(1, min(25, top_k)),
        max_rows=settings.evolution_knowledge_search_max_rows,
    )
    hits = [
        EvolutionKnowledgeHit(
            id=str(r["id"]),
            created_at=str(r["created_at"]),
            source=str(r["source"]),
            text=str(r["text"]),
            score=float(r["score"]),
            meta=r.get("meta") if isinstance(r.get("meta"), dict) else {},
        )
        for r in rows
    ]
    return EvolutionKnowledgeSearchResponse(query=query, hits=hits)


@router.post("/learn", response_model=EvolutionLearnResponse)
async def evolution_learn(request: Request, body: EvolutionLearnRequest) -> EvolutionLearnResponse:
    store = _store(request)
    payload = {"source": body.source, "summary": body.summary, "detail": body.detail}
    eid = await store.append_event(kind="learn", payload=payload)
    if body.index_knowledge and settings.evolution_knowledge_enabled and body.summary.strip():
        try:
            ollama = getattr(request.app.state, "ollama", None)
            emb = await embed_for_knowledge(settings, ollama, body.summary.strip())
            cid = await store.kg_insert(
                source=f"learn:{body.source}",
                text=body.summary.strip(),
                embedding=emb,
                meta={"learn_event_id": eid},
            )
            await store.append_event(kind="kg_ingest", payload={"chunk_id": cid, "from": "learn", "learn_event_id": eid})
        except Exception as e:
            logger.warning("learn index_knowledge failed: %s", e)
    if not body.requires_approval:
        return EvolutionLearnResponse(event_id=str(eid), pending_id=None, approval_token=None, expires_at_unix=None)
    pid = await store.insert_pending(kind="learn", payload=payload)
    tok, exp = mint_learn_approval_token(settings, pending_id=pid)
    return EvolutionLearnResponse(event_id=str(eid), pending_id=pid, approval_token=tok, expires_at_unix=int(exp))


@router.post("/approve", response_model=EvolutionApproveResponse)
async def evolution_approve(request: Request, body: EvolutionApproveRequest) -> EvolutionApproveResponse:
    store = _store(request)
    try:
        verify_learn_approval_token(settings, token=body.approval_token, pending_id=body.pending_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    row = await store.get_pending(body.pending_id)
    if not row or row.get("status") != "pending":
        raise HTTPException(status_code=400, detail="pending not found or not pending")
    await store.mark_pending(body.pending_id, "approved")
    await store.append_event(kind="learn_approved", payload={"pending_id": body.pending_id})
    return EvolutionApproveResponse(ok=True, message="pending change approved and logged")


@router.get("/twin", response_model=EvolutionTwinResponse)
async def evolution_twin_get(request: Request) -> EvolutionTwinResponse:
    store = _store(request)
    ver, payload, updated = await store.get_twin()
    return EvolutionTwinResponse(version=ver, profile=TwinProfilePayload.model_validate(payload), updated_at=updated)


@router.patch("/twin", response_model=EvolutionTwinResponse)
async def evolution_twin_patch(request: Request, body: EvolutionTwinPatchRequest) -> EvolutionTwinResponse:
    store = _store(request)
    _ver, current, _ = await store.get_twin()
    merged = merge_twin_patch(current, body.profile)
    if body.correction_note:
        m = dict(merged.meta)
        notes = list(m.get("correction_notes") or [])
        notes.append(body.correction_note[:2000])
        m["correction_notes"] = notes[-50:]
        m["last_corrected_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        merged = merged.model_copy(update={"meta": m})
    new_v, updated = await store.update_twin(merged)
    await store.append_event(
        kind="twin_patch",
        payload={"version": new_v, "note": (body.correction_note or "")[:500]},
    )
    _v2, payload2, _ = await store.get_twin()
    return EvolutionTwinResponse(version=new_v, profile=TwinProfilePayload.model_validate(payload2), updated_at=updated)


@router.post("/rollback", response_model=EvolutionRollbackResponse)
async def evolution_rollback_twin(request: Request, body: EvolutionRollbackRequest) -> EvolutionRollbackResponse:
    store = _store(request)
    ok, ver, msg = await store.rollback_twin(body.steps)
    ver_out, _, _ = await store.get_twin()
    if ok:
        await store.append_event(kind="twin_rollback", payload={"version": ver_out, "steps": body.steps})
    return EvolutionRollbackResponse(ok=ok, version=ver_out, message=msg)


@router.get("/logs", response_model=EvolutionLogsResponse)
async def evolution_logs(request: Request, limit: int = 60) -> EvolutionLogsResponse:
    store = _store(request)
    rows = await store.list_events(limit=min(limit, 200))
    entries = [
        EvolutionLogEntry(id=int(r["id"]), created_at=str(r["created_at"]), kind=str(r["kind"]), payload=r.get("payload") or {})
        for r in rows
    ]
    return EvolutionLogsResponse(entries=entries)


@router.get("/predictions")
async def evolution_predictions(request: Request) -> dict[str, object]:
    preds = build_predictions(request=request, settings=settings)
    return {"predictions": preds}
