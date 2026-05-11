# Phase 4 — Slack intelligence + work operations

## 1. Slack architecture

- **FastAPI** exposes `/slack/*` routes for OAuth, status, channel listing, synthetic “unread” summary, priority scoring, AI briefing, draft-only replies, and **optional two-step approved send**.
- **slack-sdk** `WebClient` performs workspace reads (`conversations.list`, `conversations.history`, `users.info`) and **`chat.postMessage` only after a valid signed approval token**.
- **CrewAI + Ollama** run two agents in sequence for briefings: **Slack Intel** (situation brief) then **Response Draft** (reply themes only). `/slack/draft` uses the draft agent alone.
- **Electron desktop** adds a **Slack command center** page: health, heatmap, priority cards, briefing pane, draft rail, **4C send rail** when write is enabled.
- **Phase gates**: **4A** read/analyze (default), **4B** drafts (no send), **4C** approved write (`JARVIS_SLACK_WRITE_ENABLED=true` + OAuth includes `chat:write` + explicit mint + confirm).

## 2. Environment files

| File | Purpose |
|------|--------|
| `apps/api/.env.example` | Documented template for API / Slack / Ollama. **Safe to commit.** |
| `apps/api/.env` | Your real `JARVIS_*` values (Slack client id/secret, etc.). **Gitignored.** |
| `apps/desktop/.env.example` | `VITE_API_BASE_URL`, `VITE_OLLAMA_MODEL`. **Safe to commit.** |
| `apps/desktop/.env` | Local Vite overrides. **Gitignored.** |

Copy examples to `.env` in the same folder, then fill secrets. Restart the API and `npm run dev` after edits.

## 3. OAuth setup

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps).
2. **OAuth & Permissions** → **Redirect URLs** → **Add New Redirect URL**. Paste the **exact** value shown in the JARVIS Slack hub (“Slack redirect URL”) or from `GET /slack/status` → `redirect_uri` (default: `http://127.0.0.1:8000/slack/oauth/callback`). Slack compares byte-for-byte: `http://127.0.0.1:8000/...` ≠ `http://localhost:8000/...` ≠ `https://...`. You may register multiple URLs if you switch between them. Align `JARVIS_SLACK_REDIRECT_URI` in `apps/api/.env` with whichever URL you add, then restart uvicorn. **Important:** the Slack OAuth redirect must be a **web** URL (`http://` or `https://`). Slack returns errors such as “Bot scopes are not allowed when redirecting to a non-web URI” if you register a **custom URL scheme** (`myapp://…`) as the OAuth redirect. JARVIS needs bot scopes, so use the API callback URL in Slack, then set `JARVIS_SLACK_POST_OAUTH_REDIRECT` if you want to land in the desktop app or another URL **after** the server exchanges the code. If your Slack app has **PKCE** enabled in the dashboard, prefer `127.0.0.1` over `localhost` for the redirect host (Slack may treat `localhost` as a desktop redirect).
3. **Bot token scopes**  
   - **Read (4A)**: `channels:read`, `channels:history`, `groups:read`, `groups:history`, `im:read`, `im:history`, `mpim:read`, `mpim:history`, `users:read`, `team:read`  
   - **Write (4C)**: add `chat:write` when you enable `JARVIS_SLACK_WRITE_ENABLED=true` (OAuth URL includes it automatically; **reconnect** the app after changing the flag).
4. Install app to workspace; copy **Client ID** and **Client Secret** into `apps/api/.env`.
5. Key env vars (`JARVIS_` prefix): `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_REDIRECT_URI`, `SLACK_POST_OAUTH_REDIRECT`, `SLACK_ENCRYPTION_KEY`, `SLACK_APPROVAL_SECRET`, `SLACK_WRITE_ENABLED`.

## 4. Phase 4C — Approved send

1. Set `JARVIS_SLACK_WRITE_ENABLED=true` and add `chat:write` to the Slack app; **Connect Slack** again.
2. **POST `/slack/send/prepare`** — body `{ "channel_id", "thread_ts"?, "text" }` returns `{ "approval_token", "expires_at_unix" }`. The token is an HMAC-signed payload binding **channel**, **optional thread ts**, and **SHA-256 of `text`**.
3. **POST `/slack/send`** — body `{ "approval_token", "text" }` where **`text` must be byte-identical** to step 2. On success, calls `chat.postMessage`. **No auto-send** anywhere else.

Optional: set `JARVIS_SLACK_APPROVAL_SECRET` for a dedicated HMAC key; otherwise the key is derived from client secret + encryption key material.

## 5. Slack service layer

- `app/services/slack_service.py` — OAuth exchange, scopes helper (`bot_oauth_scope_string`), channel listing, gather, priority/unread helpers, `chat_post_message`.
- `app/services/slack_send_approval.py` — mint / verify approval tokens.
- `app/services/slack_channel_prefs.py` — merges bundled defaults with `{data_dir}/slack/slack_channels.json`.
- `app/services/slack_token_store.py` — Fernet-encrypted token JSON at `{data_dir}/slack/oauth_store.json`.

## 6. Slack Intel agent

- `app/agents/slack_intel_agent.py` — used in `app/services/slack_crew_runner.py` for **Today’s Command Brief**.

## 7. Response Draft agent

- `app/agents/response_draft_agent.py` — briefing follow-up themes; `/slack/draft` for reply options. **`approval_required: true`**, **`auto_send: false`**.

## 8. Priority scoring engine

- `app/services/slack_priority_engine.py` — priority channels, VIPs, keywords, mentions, broadcast hints, volume proxy.

## 9. Dashboard Slack UI

- Route: `/slack` — status (including **Approved send** armed/off), heatmap, priority inbox, heuristic unread, briefing, drafts, **4C two-step send** when write is enabled.

## 10. Security model

- Slack bot token encrypted at rest (Fernet); tight file permissions where supported.
- Read scopes only until write flag + reinstall adds `chat:write`.
- Send path requires **two explicit HTTP steps** and matching message body; tokens are short-lived.

## 11. Testing strategy

- **Unit**: `tests/test_slack_priority.py`, `tests/test_slack_send_approval.py` (HMAC roundtrip + 403 on prepare when write disabled).
- **Manual**: OAuth → briefing; with write on → mint → send in a test channel.

## 12. Definition of done

- [x] `/slack/connect`, `/slack/oauth/callback`, `/slack/status`, `/slack/channels`, `/slack/unread`, `/slack/priority`, `/slack/briefing`, `/slack/draft`
- [x] `/slack/send/prepare`, `/slack/send` (4C, gated)
- [x] Encrypted local token store + channel prefs merge
- [x] Intel + draft CrewAI path + priority engine
- [x] Desktop Slack hub + API client helpers
- [x] `.env` / `.env.example` for API and desktop
