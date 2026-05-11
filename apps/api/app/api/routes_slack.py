from __future__ import annotations

import logging
import secrets
import time
from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.config import settings
from app.schemas.slack import (
    SlackBriefingRequest,
    SlackDraftRequest,
    SlackOAuthCallbackQuery,
    SlackSendConfirmRequest,
    SlackSendPrepareRequest,
)
from app.services.slack_crew_runner import run_slack_briefing_crew, run_slack_draft_crew
from app.services.slack_send_approval import mint_send_approval_token, verify_send_approval_token
from app.services.slack_service import (
    bot_oauth_scope_string,
    build_priority_payload,
    build_unread_style_summary,
    chat_post_message,
    gather_slack_intelligence,
    list_joined_channels,
    oauth_v2_exchange,
    slack_bot_oauth_redirect_info,
    slack_pkce_challenge_s256,
    slack_pkce_verifier,
)
from app.services.slack_token_store import load_credentials, save_credentials

logger = logging.getLogger(__name__)

router = APIRouter(tags=["slack"])

_STATE_TTL_S = 600.0


def _purge_states(states: dict[str, Any]) -> None:
    now = time.time()
    for k, v in list(states.items()):
        exp = float(v["exp"]) if isinstance(v, dict) else float(v)
        if exp < now:
            states.pop(k, None)


def _require_creds() -> Any:
    creds = load_credentials(settings)
    if creds is None:
        raise HTTPException(status_code=401, detail="Slack not connected")
    return creds


@router.get("/slack/connect", response_model=None)
async def slack_connect(request: Request) -> RedirectResponse:
    if not settings.slack_client_id.strip() or not settings.slack_client_secret.strip():
        raise HTTPException(status_code=503, detail="Slack OAuth is not configured (client id/secret)")
    ri = slack_bot_oauth_redirect_info(settings.slack_redirect_uri)
    if not ri.ok:
        raise HTTPException(status_code=400, detail=ri.issue or "Invalid Slack redirect URI")
    states: dict[str, Any] = request.app.state.slack_oauth_states
    _purge_states(states)
    state = secrets.token_urlsafe(24)
    code_verifier = slack_pkce_verifier()
    code_challenge = slack_pkce_challenge_s256(code_verifier)
    states[state] = {"exp": time.time() + _STATE_TTL_S, "code_verifier": code_verifier}
    from urllib.parse import quote

    scopes = bot_oauth_scope_string(settings)
    q = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={quote(settings.slack_client_id.strip())}"
        f"&scope={quote(scopes)}"
        f"&redirect_uri={quote(settings.slack_redirect_uri.strip())}"
        f"&state={quote(state)}"
        f"&code_challenge={quote(code_challenge)}"
        f"&code_challenge_method=S256"
    )
    return RedirectResponse(url=q, status_code=302)


@router.get("/slack/oauth/callback", response_model=None)
async def slack_oauth_callback(request: Request, q: SlackOAuthCallbackQuery) -> RedirectResponse | JSONResponse:
    if q.error:
        raise HTTPException(status_code=400, detail=f"Slack OAuth error: {q.error}")
    if not q.code or not q.state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    states: dict[str, Any] = request.app.state.slack_oauth_states
    _purge_states(states)
    entry = states.pop(q.state, None)
    if not isinstance(entry, dict):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    exp = float(entry["exp"])
    code_verifier = str(entry.get("code_verifier") or "")
    if exp < time.time() or not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    if not settings.slack_client_id.strip() or not settings.slack_client_secret.strip():
        raise HTTPException(status_code=503, detail="Slack OAuth is not configured")

    try:
        data = oauth_v2_exchange(
            client_id=settings.slack_client_id.strip(),
            client_secret=settings.slack_client_secret.strip(),
            code=q.code.strip(),
            redirect_uri=settings.slack_redirect_uri.strip(),
            code_verifier=code_verifier,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("oauth exchange failed")
        raise HTTPException(status_code=502, detail=f"OAuth exchange failed: {e}") from e

    team = data.get("team") or {}
    payload = {
        "access_token": str(data.get("access_token") or ""),
        "team_id": str(team.get("id") or ""),
        "team_name": str(team.get("name") or "") or None,
        "bot_user_id": str(data.get("bot_user_id") or "") or None,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if not payload["access_token"] or not payload["team_id"]:
        raise HTTPException(status_code=400, detail="Incomplete OAuth response")
    save_credentials(settings, payload)

    target = settings.slack_post_oauth_redirect.strip()
    if target:
        sep = "&" if "?" in target else "?"
        return RedirectResponse(url=f"{target}{sep}slack=connected", status_code=302)
    return JSONResponse({"ok": True, "team_id": payload["team_id"]})


@router.get("/slack/status")
async def slack_status() -> dict[str, Any]:
    creds = load_credentials(settings)
    write = bool(settings.slack_write_enabled)
    phase = "4c_write_approval" if write else "4a_read"
    ri = slack_bot_oauth_redirect_info(settings.slack_redirect_uri)
    out: dict[str, Any] = {
        "connected": creds is not None,
        "team_id": creds.team_id if creds else None,
        "team_name": creds.team_name if creds else None,
        "phase": phase,
        "write_enabled": write,
        "oauth_configured": bool(settings.slack_client_id.strip() and settings.slack_client_secret.strip()),
        "oauth_scopes": bot_oauth_scope_string(settings),
        "redirect_uri": settings.slack_redirect_uri.strip(),
        "post_oauth_redirect": settings.slack_post_oauth_redirect.strip(),
        "redirect_uri_ok": ri.ok,
    }
    if ri.issue:
        out["redirect_uri_issue"] = ri.issue
    if ri.note:
        out["redirect_uri_note"] = ri.note
    return out


@router.get("/slack/channels")
async def slack_channels() -> dict[str, Any]:
    creds = load_credentials(settings)
    if creds is None:
        raise HTTPException(status_code=401, detail="Slack not connected")

    def work() -> list[dict[str, Any]]:
        rows = list_joined_channels(creds.access_token)
        out: list[dict[str, Any]] = []
        for ch in rows:
            cid = str(ch.get("id") or "")
            if not cid:
                continue
            out.append(
                {
                    "id": cid,
                    "name": ch.get("name"),
                    "is_im": bool(ch.get("is_im")),
                    "is_private": bool(ch.get("is_private")),
                    "is_mpim": bool(ch.get("is_mpim")),
                }
            )
        return out

    try:
        channels = await anyio.to_thread.run_sync(work)
    except Exception as e:
        logger.exception("slack channels")
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"channels": channels}


@router.get("/slack/unread")
async def slack_unread() -> dict[str, Any]:
    req = SlackBriefingRequest(max_channels=10, messages_per_channel=35)

    def work():
        creds = _require_creds()
        return gather_slack_intelligence(
            settings=settings,
            access_token=creds.access_token,
            max_channels=req.max_channels,
            messages_per_channel=req.messages_per_channel,
        )

    try:
        g = await anyio.to_thread.run_sync(work)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("slack unread")
        raise HTTPException(status_code=502, detail=str(e)) from e
    summary = build_unread_style_summary(settings=settings, messages_flat=g.messages_flat, channels_scanned=g.channels_scanned)
    summary["gather_errors"] = g.errors
    return summary


@router.get("/slack/priority")
async def slack_priority() -> dict[str, Any]:
    req = SlackBriefingRequest(max_channels=12, messages_per_channel=50)

    def work():
        creds = _require_creds()
        return gather_slack_intelligence(
            settings=settings,
            access_token=creds.access_token,
            max_channels=req.max_channels,
            messages_per_channel=req.messages_per_channel,
        )

    try:
        g = await anyio.to_thread.run_sync(work)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("slack priority")
        raise HTTPException(status_code=502, detail=str(e)) from e
    payload = build_priority_payload(settings=settings, messages_flat=g.messages_flat)
    payload["gather_errors"] = g.errors
    return payload


@router.post("/slack/briefing")
async def slack_briefing(req: SlackBriefingRequest) -> dict[str, Any]:
    def work():
        creds = _require_creds()
        g = gather_slack_intelligence(
            settings=settings,
            access_token=creds.access_token,
            max_channels=req.max_channels,
            messages_per_channel=req.messages_per_channel,
        )
        model = (req.model or settings.default_ollama_model).strip()
        crew = run_slack_briefing_crew(settings=settings, corpus=g.corpus, model=model)
        pri = build_priority_payload(settings=settings, messages_flat=g.messages_flat)
        return g, crew, pri, model

    try:
        g, crew, pri, model = await anyio.to_thread.run_sync(work)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("slack briefing")
        raise HTTPException(status_code=502, detail=str(e)) from e

    combined = crew.briefing_markdown.rstrip() + "\n\n" + crew.draft_hints_markdown.strip()
    return {
        "briefing_markdown": combined,
        "briefing_core": crew.briefing_markdown,
        "draft_hints": crew.draft_hints_markdown,
        "priority": pri,
        "model": model,
        "gather_errors": g.errors,
        "channels_scanned": g.channels_scanned,
    }


@router.post("/slack/draft")
async def slack_draft(req: SlackDraftRequest) -> dict[str, Any]:
    _require_creds()

    ctx = (
        f"Channel: {req.channel_id}\n"
        f"Thread ts: {req.thread_ts or '(none)'}\n\n"
        f"{req.context}"
    )

    def work():
        model = (req.model or settings.default_ollama_model).strip()
        text = run_slack_draft_crew(settings=settings, context=ctx, tone=req.tone, model=model)
        return text, model

    try:
        draft_md, model = await anyio.to_thread.run_sync(work)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("slack draft")
        raise HTTPException(status_code=502, detail=str(e)) from e

    return {
        "draft_markdown": draft_md,
        "tone": req.tone,
        "model": model,
        "approval_required": True,
        "auto_send": False,
    }


def _require_write_enabled() -> None:
    if not settings.slack_write_enabled:
        raise HTTPException(
            status_code=403,
            detail="Slack write is disabled. Set JARVIS_SLACK_WRITE_ENABLED=true and re-authorize with chat:write.",
        )


@router.post("/slack/send/prepare")
async def slack_send_prepare(req: SlackSendPrepareRequest) -> dict[str, Any]:
    _require_write_enabled()
    _require_creds()
    try:
        token, exp = mint_send_approval_token(
            settings,
            channel_id=req.channel_id,
            thread_ts=req.thread_ts,
            text=req.text,
        )
    except Exception as e:
        logger.exception("send prepare")
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "approval_token": token,
        "expires_at_unix": exp,
        "message": "Confirm with POST /slack/send using the same exact text within the token TTL.",
    }


@router.post("/slack/send")
async def slack_send(req: SlackSendConfirmRequest) -> dict[str, Any]:
    _require_write_enabled()
    creds = _require_creds()
    try:
        payload = verify_send_approval_token(settings, token=req.approval_token, text=req.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    def work() -> dict[str, Any]:
        return chat_post_message(
            access_token=creds.access_token,
            channel_id=payload.channel_id,
            text=req.text,
            thread_ts=payload.thread_ts,
        )

    try:
        out = await anyio.to_thread.run_sync(work)
    except Exception as e:
        logger.exception("slack send")
        raise HTTPException(status_code=502, detail=str(e)) from e

    if not out.get("ok"):
        raise HTTPException(status_code=502, detail=out.get("error") or "slack_post_failed")
    return {
        "ok": True,
        "ts": out.get("ts"),
        "channel": out.get("channel"),
        "auto_send": False,
        "note": "Posted via explicit two-step approval only.",
    }
