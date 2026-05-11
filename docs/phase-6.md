# Phase 6 — System evolution (self-health, intelligence, safe change)

## Health score semantics

`GET /system/health` → **`health_score`** is computed from **core** subsystems only (those with `optional_for_score: false`). Rows with `optional_for_score: true` are still returned for transparency but do not lower the score.

- **Hammerspoon** is always informational for the score: it is a **Mac HTTP bridge** to the Hammerspoon app, not a Linux `systemctl` service. Start the bridge from your Mac automation setup; do not use `systemctl`.
- **`open_interpreter_sibling`** is excluded from the score when **`JARVIS_INTERPRETER_ENABLED=false`**. Start the process from the Control deck or sibling API when you need it.
- **`crewai_sibling`** is informational unless you rely on it for daily work (same sibling API).

## Goals

- **Observe**: aggregated `/system/health`, optional `/system/performance`, log tail at `/system/logs`.
- **Diagnose**: CrewAI **self-healing** narrative (`POST /system/repair`) and **code audit** synthesis (`POST /system/audit`, `POST /system/improve`).
- **Remember**: local SQLite at `{JARVIS_DATA_DIR}/system/evolution.sqlite3` (incidents, audits, patch rows).
- **Change safely**: `POST /system/improve/prepare` → signed token → `POST /system/improve/apply` only when `JARVIS_SYSTEM_PATCHES_ENABLED=true` and the working tree is clean. Rollback: `POST /system/rollback/prepare` then `POST /system/rollback`.

## Architecture

- **Routes**: [`apps/api/app/api/routes_system.py`](../apps/api/app/api/routes_system.py)
- **Diagnostics**: [`apps/api/app/services/diagnostics_service.py`](../apps/api/app/services/diagnostics_service.py)
- **Static tools** (optional): [`apps/api/app/services/static_analysis_runner.py`](../apps/api/app/services/static_analysis_runner.py)
- **Patch / rollback**: [`apps/api/app/services/patch_service.py`](../apps/api/app/services/patch_service.py), [`apps/api/app/services/system_patch_approval.py`](../apps/api/app/services/system_patch_approval.py)
- **Store**: [`apps/api/app/services/system_evolution_store.py`](../apps/api/app/services/system_evolution_store.py)
- **Agents**: [`apps/api/app/agents/self_healing_agent.py`](../apps/api/app/agents/self_healing_agent.py), [`apps/api/app/agents/code_audit_agent.py`](../apps/api/app/agents/code_audit_agent.py)
- **Desktop**: [`apps/desktop/src/features/evolution/SystemEvolutionPage.tsx`](../apps/desktop/src/features/evolution/SystemEvolutionPage.tsx) (route `/evolution`)

## Autowork (bounded self-maintenance)

Opt-in maintenance loop for the monorepo under `JARVIS_REPO_ROOT`:

- **`GET /system/autowork/status`** — last run JSON, restart-request file presence.
- **`POST /system/autowork/tick`** — requires `JARVIS_AUTOWORK_ENABLED=true`. Runs `run_repo_checks` when subprocesses are allowed, optional `poetry install` / `ruff --fix` / `npm run build`, and logs `autowork_tick` to Phase 8 evolution events.
- **Scheduler:** `JARVIS_AUTOWORK_SCHEDULE_ENABLED=true` with the same `AUTOWORK_ENABLED` gate.
- **Restart:** the API **never** kills itself. With `JARVIS_AUTOWORK_RESTART_REQUEST_ON_GREEN=true`, a green `repo_checks` run writes `data_dir/autowork/RESTART_REQUESTED.json` for an external supervisor or you to restart.
- **Code changes** still use the signed patch flow (`/system/improve/*`) — autowork does not auto-apply diffs.

## Autonomy tier (Phase 3 rail)

| Value | Effect |
|-------|--------|
| `JARVIS_AUTONOMY_TIER=standard` (default) | Medium-risk automation steps still require a **challenge** token on `POST /workflows/run` and `POST /execute` before Hammerspoon runs. |
| `JARVIS_AUTONOMY_TIER=elevated` | **Confirm**-tier steps run on the first POST (no second confirmation). **Restricted** patterns (e.g. `sudo`, destructive shell) stay blocked. Kill switch, sandbox, Slack send tokens, and git patch apply are **unchanged**. |

Bypasses are written to the action log as `elevated_autonomy_confirm_tier_bypassed`. This is not macOS “super admin” and does not bypass TCC.

## Environment

| Variable | Purpose |
|----------|---------|
| `JARVIS_AUTONOMY_TIER` | `standard` or `elevated` — see table above. |
| `JARVIS_REPO_ROOT` | Absolute path to git monorepo root (patches, `git apply`, optional audits). |
| `JARVIS_SYSTEM_ALLOW_SUBPROCESS` | When `true`, `POST /system/audit` with `run_tools: true` may run `ruff` / `mypy` / `pytest` under `apps/api`. |
| `JARVIS_SYSTEM_PATCHES_ENABLED` | Must be `true` to allow `improve/apply` and `rollback`. |
| `JARVIS_SYSTEM_PATCH_SECRET` | Optional HMAC key for patch/rollback tokens. |
| `JARVIS_SYSTEM_METRICS_ENABLED` | Set `true` and install **psutil** for CPU/RAM in `/system/performance`. |
| `JARVIS_SYSTEM_LOG_MAX_BYTES` / `JARVIS_SYSTEM_LOG_BACKUP_COUNT` | Rotating `data_dir/logs/api.log`. |

## Security

- No silent file edits: apply requires **token + identical diff bytes** and env gate.
- Subprocesses for audits are **off by default** and require `JARVIS_REPO_ROOT`.
- Patch flow uses a **dedicated git branch** `jarvis-evolve-*`; failed pytest runs trigger **reverse apply** and branch deletion when possible.

## Operator workflow (patches)

1. Ensure `JARVIS_REPO_ROOT` points at the repo and `git status` is clean.
2. `POST /system/improve/prepare` with unified diff body → receive `approval_token`, `patch_id`, `branch_name`, `base_sha`.
3. Set `JARVIS_SYSTEM_PATCHES_ENABLED=true`, restart API if needed.
4. `POST /system/improve/apply` with the **same** `diff_text` and `approval_token`.
5. To undo after success: checkout remains on evolve branch with changes applied as working tree — use `rollback/prepare` + `rollback` while still on that branch (see API responses).

## Testing

- API: `pytest tests/test_system_phase6.py`
- Full suite: `pytest` under `apps/api/`

## Definition of done (Phase 6 v1)

- [x] Aggregated health + score
- [x] Incidents + audit persistence
- [x] Repair and audit Crew paths (stub when `JARVIS_LLM_STUB=true`)
- [x] Patch prepare/apply/rollback with HMAC tokens
- [x] Desktop Evolution console
- [x] Rotating API log file (when lifespan runs with settings)

Deferred (6.1+): ESLint/bundle-size in CI, richer perf dashboards, auth.test Slack probe, automated dependency upgrades.
