# Phase 1 — Foundation MVP

## Objectives

- Ship a production-shaped **Electron + React** desktop shell with a cinematic **JARVIS OS** HUD.
- Provide a minimal **FastAPI** service with `/health` and `/version` for connectivity checks.
- Persist **local configuration** (API URL, accent) under the Electron `userData` path via **narrow IPC** (`jarvis:v1:*`).

## Features

| Area | Description |
|------|-------------|
| Boot | Animated startup at `/` with skip + auto-route to `/dashboard`. |
| Shell | Sidebar navigation, top bar, API status pill (polls `/health` every 5s). |
| Dashboard | Overview tiles and links into Agents / Metrics / Console. |
| Agents | Mock agent roster with status + load visuals. |
| Metrics | Recharts area chart with **simulated** CPU/RAM series. |
| Console | Transcript + input; deterministic “Phase 2” placeholder responses. |
| Settings | Edit API base URL + accent; save/reset via IPC-backed JSON. |
| API | `GET /health`, `GET /version`, CORS for local Vite origins. |

## Folder map

- [`apps/desktop`](../apps/desktop) — Electron main/preload, Vite renderer, UI features.
- [`apps/api`](../apps/api) — FastAPI application package.
- [`scripts/dev-all.sh`](../scripts/dev-all.sh) — Optional API-only helper (see script header).

## Runbook

### Prerequisites

- Node.js **20+** (LTS recommended).
- Python **3.11+**.

### API

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Desktop

From repository root:

```bash
npm install
npm run dev
```

The renderer expects the API at `http://127.0.0.1:8000` by default (override in **Settings** or `VITE_API_BASE_URL` at build time).

### Optional: background API

```bash
./scripts/dev-all.sh
```

Then run `npm run dev` from the repo root in a second terminal.

## Environment

| Variable | Where | Purpose |
|----------|-------|---------|
| `JARVIS_CORS_ORIGINS` | `apps/api` | Comma-separated allowed origins (default includes Vite dev URLs). |
| `VITE_API_BASE_URL` | `apps/desktop` build | Default API URL when no saved config exists (non-Electron / first boot). |
| `JARVIS_OPEN_DEVTOOLS` | Electron dev | Set to `1` to auto-open DevTools when `ELECTRON_RUN_AS_NODE` is not set and app is unpackaged. |

## Routing

The renderer uses **React Router `HashRouter`** so client routes work when the UI is loaded from Electron’s `file://` production bundle (`dist/index.html`).

## Security notes (Phase 1)

- Renderer: **`contextIsolation: true`**, **`nodeIntegration: false`**, **`sandbox: true`**, minimal **`preload`** surface.
- IPC payloads are validated with **Zod** in the main process before writing `config.json`.
- **No** remote content loading; `window.open` is denied; navigation is restricted in the main window.
- **CSP**: tighten before distribution (Vite dev may require relaxed script policy — treat as dev-only gap).

## Definition of done (Phase 1)

- [ ] Boot → dashboard flow feels polished; navigation covers all Phase 1 routes.
- [ ] API status pill reflects live `/health` when API is running.
- [ ] Settings persist across app restarts.
- [ ] `pytest` passes in `apps/api`; `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build` pass in `apps/desktop`.

## Testing strategy

- **Desktop**: Vitest unit test for `cn()`; manual macOS smoke (boot, save settings, console).
- **API**: Pytest for `/health`, `/version`, and CORS preflight.

## Risks & next hooks

| Risk | Mitigation |
|------|------------|
| Electron + Vite plugin drift | Pin versions; use repo `package-lock.json`. |
| IPC creep | Add new channels only with `jarvis:v1:` prefix and main-process validation. |

**Phase 2 hooks**: extend [`apps/desktop/src/lib/api.ts`](../apps/desktop/src/lib/api.ts) for chat/stream routes; replace mock agents with API-driven state.
