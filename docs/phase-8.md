# Phase 8 — Digital executive twin, idle learning, evolution lab

## Architecture

| Layer | Location |
|-------|----------|
| API | [`apps/api/app/api/routes_evolution.py`](../apps/api/app/api/routes_evolution.py) — prefix `/evolution` |
| Store | [`apps/api/app/services/evolution_store.py`](../apps/api/app/services/evolution_store.py) — `{data_dir}/evolution/phase8.sqlite3` |
| Idle synthesis | [`idle_learning_service.py`](../apps/api/app/services/idle_learning_service.py), [`idle_learning_crew_runner.py`](../apps/api/app/services/idle_learning_crew_runner.py) |
| Scheduled idle (8.1) | [`idle_scheduler.py`](../apps/api/app/services/idle_scheduler.py) — opt-in asyncio loop in [`main.py`](../apps/api/app/main.py) lifespan |
| Twin merge | [`personality_alignment_service.py`](../apps/api/app/services/personality_alignment_service.py) |
| Predictive hints | [`predictive_diagnostics.py`](../apps/api/app/services/predictive_diagnostics.py) |
| Learn approval HMAC | [`evolution_approval.py`](../apps/api/app/services/evolution_approval.py) |
| Sandbox registry | [`sandbox_evolution_service.py`](../apps/api/app/services/sandbox_evolution_service.py) |
| Sandbox benchmark | [`sandbox_bench_service.py`](../apps/api/app/services/sandbox_bench_service.py) → `static_analysis_runner.run_repo_checks` |
| Local KG + vectors | [`kg_chunks` in evolution_store](../apps/api/app/services/evolution_store.py), [`evolution_embeddings.py`](../apps/api/app/services/evolution_embeddings.py), [`knowledge_embedding.py`](../apps/api/app/services/knowledge_embedding.py) |
| Ollama embeddings | [`ollama_client.py`](../apps/api/app/services/ollama_client.py) `embed()` |
| Agents (definitions) | [`twin_agent.py`](../apps/api/app/agents/twin_agent.py), [`idle_learning_agent.py`](../apps/api/app/agents/idle_learning_agent.py), [`evolution_agent.py`](../apps/api/app/agents/evolution_agent.py) |
| Desktop | [`EvolutionLabPage.tsx`](../apps/desktop/src/features/evolution/EvolutionLabPage.tsx) — route **`/evolution-lab`** (Phase 6 **System** console stays at `/evolution`) |

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/evolution/status` | Twin version, confidence map, idle metadata, **idle schedule**, **knowledge chunk count**, pending approvals, strategic maturity index |
| POST | `/evolution/idle` | One bounded idle cycle (Crew + logs + health + optional **KG digest**); persisted to `idle_runs` |
| GET | `/evolution/sandbox` | Sandbox-related events + pending sandbox rows |
| POST | `/evolution/sandbox` | Record sandbox proposal + pending row |
| POST | `/evolution/sandbox/benchmark` | Run **Phase 6** ruff/mypy/pytest under `JARVIS_REPO_ROOT` (when subprocess allowed); log `sandbox_benchmark` |
| GET | `/evolution/knowledge/status` | Chunk count + last ingest time |
| POST | `/evolution/knowledge/ingest` | Embed text (Ollama or stub) → `kg_chunks` |
| GET | `/evolution/knowledge/search` | `?q=` cosine search over recent chunks |
| POST | `/evolution/learn` | Append learning event; optional `requires_approval` + HMAC token; optional **`index_knowledge`** |
| POST | `/evolution/approve` | Approve pending learn row with token |
| GET | `/evolution/twin` | Current twin JSON profile |
| PATCH | `/evolution/twin` | Merge profile dimensions + optional `correction_note` |
| POST | `/evolution/rollback` | Roll back twin to previous stored version (steps 1–20) |
| GET | `/evolution/logs` | Recent evolution audit events |
| GET | `/evolution/predictions` | Local heuristics only (no network) |

## Ethics and boundaries

- **No identity delegation:** twin models *style and workflow preferences* for UX alignment — not permission to act as the user on external systems.
- **No silent mutation:** idle output is advisory; code changes remain Phase 6 `/system/improve/*` with tokens + env gates.
- **No web crawl** in idle learning inputs — health JSON, API log tail, twin snapshot, and **retrieved local `kg_chunks` only** (no external fetch).
- **Emergency reset:** `POST /evolution/rollback` on the twin profile; delete `{data_dir}/evolution/phase8.sqlite3` for full twin reset (destructive).

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `JARVIS_EVOLUTION_IDLE_ENABLED` | `true` | Set `false` to disable manual and scheduled idle learning. |
| `JARVIS_EVOLUTION_IDLE_SCHEDULE_ENABLED` | `false` | Set `true` to start the background idle loop (still bounded; same inputs as `POST /evolution/idle`). |
| `JARVIS_EVOLUTION_IDLE_SCHEDULE_INTERVAL_S` | `3600` | Seconds between ticks (300–86400). First tick runs after one full interval from process start. |
| `JARVIS_EVOLUTION_KNOWLEDGE_ENABLED` | `true` | Master switch for `/evolution/knowledge/*` and idle KG retrieval. |
| `JARVIS_EVOLUTION_KNOWLEDGE_EMBED_MODEL` | *(empty)* | Ollama embedding model; empty uses `JARVIS_DEFAULT_OLLAMA_MODEL`. |
| `JARVIS_EVOLUTION_KNOWLEDGE_SEARCH_MAX_ROWS` | `800` | Cap on recent rows scanned per similarity search. |

Learn-approval tokens derive from `JARVIS_SYSTEM_PATCH_SECRET` / Slack secret material (same family as Phase 6 patch tokens).

### Phase 8.1 — step 1: scheduled idle

1. **Opt-in:** `JARVIS_EVOLUTION_IDLE_SCHEDULE_ENABLED` defaults **off**.
2. **Same contract:** each tick matches `POST /evolution/idle`.
3. **Shutdown:** asyncio task cancelled on Uvicorn lifespan exit.

### Phase 8.1 — step 2: local knowledge graph (vectors in SQLite)

1. **Storage:** table `kg_chunks` in the same `phase8.sqlite3` (text + `embedding_json` + metadata).
2. **Embeddings:** `POST /api/embeddings` via Ollama when stub is off; **`JARVIS_LLM_STUB`** uses deterministic unit vectors (384-D) for reproducible tests.
3. **Search:** cosine similarity in-process over the most recent N rows (`JARVIS_EVOLUTION_KNOWLEDGE_SEARCH_MAX_ROWS`).
4. **Ingestion:** explicit `POST /evolution/knowledge/ingest`, or `POST /evolution/learn` with **`index_knowledge: true`**.

### Phase 8.1 — step 3: safety + drift tests (CI)

Pytest modules [`tests/test_evolution_safety_phase81.py`](../apps/api/tests/test_evolution_safety_phase81.py) and [`tests/test_evolution_knowledge_phase81.py`](../apps/api/tests/test_evolution_knowledge_phase81.py) run in the standard API CI job (see [`.github/workflows/jarvis-api-ci.yml`](../.github/workflows/jarvis-api-ci.yml)).

### Phase 8.1 — step 4: sandbox ↔ git benchmark

`POST /evolution/sandbox/benchmark` calls the same **`run_repo_checks`** stack as Phase 6 audits when **`JARVIS_REPO_ROOT`** and **`JARVIS_SYSTEM_ALLOW_SUBPROCESS=true`**. Results are summarized in the JSON response and appended to **`evolution_events`** (`sandbox_benchmark`). Production code is still not mutated automatically.

## Definition of done (Phase 8 v1)

- [x] `/evolution/*` routes implemented and registered
- [x] SQLite twin + history + idle runs + events + pending
- [x] Idle learning crew (Ollama) with `JARVIS_LLM_STUB` fallback
- [x] Twin PATCH merge + rollback + correction notes
- [x] Learn + approve HMAC flow
- [x] Predictive heuristics endpoint
- [x] Evolution Lab UI
- [x] Tests: [`tests/test_evolution_phase8.py`](../apps/api/tests/test_evolution_phase8.py), safety/KB in `test_evolution_*_phase81.py`

**Still optional later:** dedicated Chroma/Lance server, automated multi-repo benchmarks, richer graph edges beyond chunk similarity.
