# Phase 2 — Local Brain

## Objectives

- Route console commands through **FastAPI `POST /command`** into a **CrewAI** sequential crew (**Planner → Commander**) backed by **Ollama**.
- Persist **session memory** locally in **SQLite** (`JARVIS_DATA_DIR`, default `.jarvis_data/memory.sqlite3`).
- Expose **model discovery**, **agent roster**, and **memory inspection** endpoints for the Electron HUD.

## Prerequisites

1. **Ollama** installed for macOS arm64 and running (default `http://127.0.0.1:11434`).
2. Pull at least one model, for example:

   ```bash
   ollama pull llama3
   ollama pull qwen2.5-coder
   ```

3. Python **3.11+** and Node **20+** as in [macos-setup.md](macos-setup.md).

## Run

**API**

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Desktop**

```bash
npm install
npm run dev
```

## Environment variables (`JARVIS_*`)

| Variable | Purpose |
|----------|---------|
| `JARVIS_OLLAMA_BASE_URL` | Ollama HTTP base (default `http://127.0.0.1:11434`). |
| `JARVIS_DEFAULT_OLLAMA_MODEL` | Server default tag when the client omits `model` (default `llama3`). |
| `JARVIS_DATA_DIR` | Directory for SQLite + local artifacts (default `.jarvis_data`). |
| `JARVIS_LLM_STUB` | When `true`/`1`, `/command` returns deterministic output without calling CrewAI/Ollama (CI / offline dev). |
| `JARVIS_CREW_VERBOSE` | Enables verbose CrewAI logging when `true`. |
| `JARVIS_CORS_ORIGINS` | Comma-separated CORS allowlist for the renderer. |

## HTTP surface

| Method | Path | Notes |
|--------|------|------|
| GET | `/health` | Adds `ollama: { reachable, error? }`. |
| GET | `/version` | `0.2.0` series. |
| GET | `/models` | Lists installed Ollama tags + recommended defaults. |
| POST | `/command` | `{ message, session_id, model? }` — runs crew, writes memory + agent events. |
| GET | `/agents/status` | Static registry + optional `session_id` scoped last events. |
| GET | `/memory?session_id=` | Recent transcript slice. |
| POST | `/memory` | `{ session_id, role, content }` manual append. |

## Desktop configuration

Persisted JSON (via Electron IPC) now includes **`ollamaModel`** (tag without `ollama/` prefix). The Settings screen loads `/models` to populate datalist suggestions.

## Testing

```bash
cd apps/api && source .venv/bin/activate && pytest
```

Stub path: tests temporarily set `settings.llm_stub = True` with an isolated `JARVIS_DATA_DIR` under pytest `tmp_path`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `/command` errors mentioning LiteLLM / Ollama | Model pulled? `ollama list` shows tag? Try full tag in Settings (e.g. `llama3:latest`). |
| Crew import errors | Reinstall `pip install -e ".[dev]"` after pulling latest `pyproject.toml`. |
| SQLite permission errors | Ensure `JARVIS_DATA_DIR` is writable. |

## Next phases

- **Phase 3**: Open Interpreter + Hammerspoon action layer.
- **Phase 4**: Slack agent implementation (currently registered as disabled in `/agents/status`).
