# Phase 3 — Computer control + macOS automation

## Overview

Phase 3 adds a **permission-gated execution rail**: JSON workflow profiles, a **Hammerspoon HTTP bridge** for native actions, optional **sandbox** dry-run, a **global kill switch**, and a **Control** screen in the Electron app.

Natural-language chat remains on **`POST /command`** (Phase 2). **Automation never runs from chat alone**; operators use **`POST /workflows/run`** or **`POST /execute`** with explicit confirmation when required.

## Hammerspoon bridge

1. Install [Hammerspoon](https://www.hammerspoon.org/).
2. Copy [`automation/hammerspoon/jarvis_bridge.lua`](../automation/hammerspoon/jarvis_bridge.lua) into `~/.hammerspoon/` (or `require` it from `~/.hammerspoon/init.lua`).
3. Set the same token the API uses:

   ```bash
   export JARVIS_HS_TOKEN="your-long-random-secret"
   ```

   Match in the API `.env` or environment: `JARVIS_HAMMERSPOON_TOKEN` (see `app/core/config.py` field `hammerspoon_token`).

4. Reload Hammerspoon. The script listens on **`http://127.0.0.1:17339`** by default (`GET /health`, `POST /jarvis`).

5. API base URL for the bridge defaults to `JARVIS_HAMMERSPOON_URL` (`http://127.0.0.1:17339`).

**Security:** the server binds to localhost; always use a strong random bearer token. Do not expose this port beyond your machine.

## API routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/permissions/check` | Classify steps (`safe` / `confirm` / `restricted`) |
| POST | `/workflows/run` | Run a profile; may return `pending` + `challenge` for confirmation |
| POST | `/execute` | Run explicit JSON steps (same confirmation rules) |
| GET | `/system/status` | Armed state, sandbox, Hammerspoon reachability, recent action log tail |
| POST | `/kill` | Disarm automation (blocks `/workflows/run` and `/execute`) |
| POST | `/system/arm` | `{ "armed": true }` to re-enable after kill |
| GET | `/automation/profiles` | List bundled profiles |

## Environment

| Variable | Purpose |
|----------|---------|
| `JARVIS_AUTOMATION_SANDBOX` | `true` — log only, no Hammerspoon calls |
| `JARVIS_HAMMERSPOON_URL` | Bridge base URL |
| `JARVIS_HAMMERSPOON_TOKEN` | Bearer token shared with Lua |
| `JARVIS_INTERPRETER_ENABLED` | Reserved; bounded interpreter path is gated by default |
| `JARVIS_DATA_DIR` | SQLite + `logs/actions.log` |

## Workflow profiles

Bundled JSON lives under [`apps/api/app/automation/profiles/`](../apps/api/app/automation/profiles/) (`morning`, `coding`, `meetings`, `quick`). Edit or add files there and restart the API.

## Desktop

Open **Control** in the sidebar for:

- Preset workflow buttons  
- Kill switch + re-arm  
- Confirmation modal when the server returns `pending`  
- Live status + recent log tail from `/system/status`

## Troubleshooting

| Issue | Check |
|-------|--------|
| Hammerspoon DOWN | Bridge running? Token matches? Port 17339 free? |
| `automation_disarmed` | Click **Re-arm** or `POST /system/arm` with `{"armed":true}` |
| Actions logged but nothing launches | `JARVIS_AUTOMATION_SANDBOX` — set to `false` for real calls |
| Lua errors | Hammerspoon console — API may differ slightly by version; adjust `jarvis_bridge.lua` |

## Open Interpreter

Full unconstrained interpreter execution is **not** enabled in this phase. Keep using explicit workflows and JSON `ActionPlan` steps until a future hardening pass adds a strictly sandboxed interpreter pipeline.
