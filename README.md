# JARVIS — personal AI command center

Phase 1–3 add a local-first desktop shell (Electron + React), a FastAPI **local brain** (Ollama + CrewAI), and a **permission-gated control rail** (Hammerspoon + workflows + kill switch). See [docs/phase-1.md](docs/phase-1.md), [docs/phase-2.md](docs/phase-2.md), [docs/phase-3.md](docs/phase-3.md), and [docs/macos-setup.md](docs/macos-setup.md).

## Quick start

**API (terminal 1)**

```bash
cd apps/api && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Desktop (terminal 2)**

```bash
npm install && npm run dev
```

Optional: `./scripts/dev-all.sh` starts the API in the background and prints the desktop command.

## Structure

- `apps/desktop` — Electron + Vite + React (JARVIS OS UI)
- `apps/api` — FastAPI (`/health`, `/version`)
