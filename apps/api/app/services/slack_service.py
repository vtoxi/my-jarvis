from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import string
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.core.config import Settings
from app.schemas.slack import SlackChannelPrefs
from app.services.slack_channel_prefs import load_slack_channel_prefs
from app.services.slack_priority_engine import rank_messages

logger = logging.getLogger(__name__)

READ_BOT_SCOPES = (
    "channels:read,channels:history,groups:read,groups:history,"
    "im:read,im:history,mpim:read,mpim:history,users:read,team:read"
)
WRITE_BOT_SCOPE = "chat:write"


def bot_oauth_scope_string(settings: Settings) -> str:
    base = READ_BOT_SCOPES
    if settings.slack_write_enabled:
        return f"{base},{WRITE_BOT_SCOPE}"
    return base


def chat_post_message(*, access_token: str, channel_id: str, text: str, thread_ts: str | None = None) -> dict[str, Any]:
    client = WebClient(token=access_token)
    kwargs: dict[str, Any] = {"channel": channel_id, "text": text}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    try:
        resp = client.chat_postMessage(**kwargs)
    except SlackApiError as e:
        err = e.response.get("error") if e.response else str(e)
        return {"ok": False, "error": err}
    if isinstance(resp, dict):
        return dict(resp)
    data = getattr(resp, "data", None)
    return dict(data) if isinstance(data, dict) else {"ok": bool(getattr(resp, "status_code", 200) == 200)}


@dataclass
class SlackGatherResult:
    corpus: str
    messages_flat: list[dict[str, Any]]
    channels_scanned: list[dict[str, Any]]
    errors: list[str] = field(default_factory=list)


_PKCE_UNRESERVED = string.ascii_letters + string.digits + "-._~"


def slack_pkce_verifier(length: int = 64) -> str:
    """RFC 7636 code_verifier (43–128 chars from unreserved alphabet)."""
    lo, hi = 43, 128
    n = max(lo, min(hi, length))
    return "".join(secrets.choice(_PKCE_UNRESERVED) for _ in range(n))


def slack_pkce_challenge_s256(verifier: str) -> str:
    """RFC 7636 S256 code_challenge (base64url without padding)."""
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SlackBotOAuthRedirectInfo:
    """Slack rejects bot workspace installs for non-web redirect URIs (custom schemes, etc.)."""

    ok: bool
    issue: str | None = None
    note: str | None = None


def slack_bot_oauth_redirect_info(redirect_uri: str) -> SlackBotOAuthRedirectInfo:
    """
    Bot token OAuth requires a web redirect (http/https). Custom URL schemes are not supported
    for bot scopes (Slack: "Bot scopes are not allowed when redirecting to a non-web URI").
    Use JARVIS_SLACK_POST_OAUTH_REDIRECT to open the desktop app after the API callback.
    """
    from urllib.parse import urlparse

    raw = (redirect_uri or "").strip()
    if not raw:
        return SlackBotOAuthRedirectInfo(
            ok=False,
            issue=(
                "JARVIS_SLACK_REDIRECT_URI is empty. Use a web callback URL, for example "
                "http://127.0.0.1:8000/slack/oauth/callback, and register it under Slack app → OAuth & Permissions → Redirect URLs."
            ),
        )
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return SlackBotOAuthRedirectInfo(
            ok=False,
            issue=(
                "Slack does not allow bot scopes when the OAuth Redirect URL is a non-web URI "
                "(for example myapp://oauth). Register an http(s) URL that hits this API "
                "(e.g. http://127.0.0.1:8000/slack/oauth/callback), set JARVIS_SLACK_REDIRECT_URI to match, "
                "and use JARVIS_SLACK_POST_OAUTH_REDIRECT if you need a custom scheme or app URL after install."
            ),
        )
    if not parsed.netloc:
        return SlackBotOAuthRedirectInfo(ok=False, issue="JARVIS_SLACK_REDIRECT_URI must include a host (e.g. 127.0.0.1:8000).")
    note: str | None = None
    if (parsed.hostname or "").lower() == "localhost":
        note = (
            "If your Slack app has PKCE enabled in the Slack dashboard, localhost may be treated as a desktop redirect "
            "and bot installs can fail; prefer http://127.0.0.1:8000/… for JARVIS_SLACK_REDIRECT_URI."
        )
    return SlackBotOAuthRedirectInfo(ok=True, note=note)


def oauth_v2_exchange(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
) -> dict[str, Any]:
    body: dict[str, str] = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    if code_verifier is not None:
        body["code_verifier"] = code_verifier
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://slack.com/api/oauth.v2.access",
            data=body,
        )
        r.raise_for_status()
        data = r.json()
    if not data.get("ok"):
        raise ValueError(str(data.get("error") or "oauth_failed"))
    return data


def _client(token: str) -> WebClient:
    return WebClient(token=token)


def list_joined_channels(access_token: str) -> list[dict[str, Any]]:
    return _list_all_conversations(_client(access_token))


def _list_all_conversations(client: WebClient) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        try:
            resp = client.conversations_list(
                limit=200,
                cursor=cursor,
                types="public_channel,private_channel,mpim,im",
                exclude_archived=True,
            )
        except SlackApiError as e:
            logger.warning("conversations_list failed: %s", e)
            break
        if not resp.get("ok"):
            logger.warning("conversations_list not ok: %s", resp.get("error"))
            break
        out.extend(resp.get("channels") or [])
        cursor = resp.get("response_metadata", {}).get("next_cursor") or None
        if not cursor:
            break
    return out


def _user_label(client: WebClient, user_id: str, cache: dict[str, str]) -> str:
    if user_id in cache:
        return cache[user_id]
    try:
        info = client.users_info(user=user_id)
        if info.get("ok") and info.get("user"):
            u = info["user"]
            prof = u.get("profile") or {}
            label = (prof.get("display_name") or prof.get("real_name") or u.get("name") or user_id).strip()
            cache[user_id] = label or user_id
            return cache[user_id]
    except SlackApiError:
        pass
    cache[user_id] = user_id
    return user_id


def _channel_sort_key(ch: dict[str, Any], prefs: SlackChannelPrefs) -> tuple[int, str]:
    cid = str(ch.get("id") or "")
    pri = 0 if cid in prefs.priority_channel_ids else 1
    name = str(ch.get("name") or ch.get("user") or cid)
    return (pri, name)


def gather_slack_intelligence(
    *,
    settings: Settings,
    access_token: str,
    max_channels: int,
    messages_per_channel: int,
) -> SlackGatherResult:
    prefs = load_slack_channel_prefs(settings)
    client = _client(access_token)
    convs = _list_all_conversations(client)
    convs.sort(key=lambda c: _channel_sort_key(c, prefs))
    user_cache: dict[str, str] = {}
    lines: list[str] = []
    flat: list[dict[str, Any]] = []
    scanned_meta: list[dict[str, Any]] = []
    errors: list[str] = []

    now = time.time()
    lines.append(f"Slack snapshot window: recent history per channel (as of {int(now)}).")
    lines.append("Monitored priority channel IDs: " + (", ".join(prefs.priority_channel_ids) or "(none configured)"))
    lines.append("")

    picked = 0
    for ch in convs:
        if picked >= max_channels:
            break
        cid = str(ch.get("id") or "")
        if not cid:
            continue
        is_im = ch.get("is_im") is True
        is_mpim = ch.get("is_mpim") is True
        label = str(ch.get("name") or "")
        if is_im:
            label = "DM:" + _user_label(client, str(ch.get("user") or ""), user_cache)
        elif is_mpim:
            label = label or "mpim"
        elif not label:
            label = cid

        try:
            hist = client.conversations_history(channel=cid, limit=messages_per_channel)
        except SlackApiError as e:
            errors.append(f"{cid}:{e.response.get('error') if e.response else e}")
            continue
        if not hist.get("ok"):
            errors.append(f"{cid}:{hist.get('error')}")
            continue

        msgs = list(hist.get("messages") or [])
        if not msgs:
            continue
        picked += 1
        vol = len(msgs)
        importance = 1.15 if cid in prefs.priority_channel_ids else 0.55
        if is_im:
            importance += 0.35
        scanned_meta.append({"id": cid, "name": label, "message_count": vol, "importance": importance})

        lines.append(f"### Channel `{label}` ({cid}) — {vol} messages")
        for m in reversed(msgs[-messages_per_channel:]):
            if m.get("subtype") in ("channel_join", "channel_leave", "bot_message"):
                continue
            text = str(m.get("text") or "").replace("\n", " ").strip()
            if not text:
                continue
            uid = str(m.get("user") or "")
            who = _user_label(client, uid, user_cache) if uid else "unknown"
            ts = str(m.get("ts") or "")
            lines.append(f"- [{ts}] {who}: {text[:500]}")
            flat.append(
                {
                    "channel_id": cid,
                    "channel_name": label,
                    "user_id": uid or None,
                    "ts": ts,
                    "text": text,
                    "channel_importance": importance,
                    "channel_message_volume": vol,
                }
            )
        lines.append("")

    corpus = "\n".join(lines).strip()
    if not corpus:
        corpus = "(No readable Slack messages in selected channels.)"

    return SlackGatherResult(corpus=corpus, messages_flat=flat, channels_scanned=scanned_meta, errors=errors)


def build_priority_payload(
    *,
    settings: Settings,
    messages_flat: list[dict[str, Any]],
    top_n: int = 40,
) -> dict[str, Any]:
    prefs = load_slack_channel_prefs(settings)
    ranked = rank_messages(messages_flat, prefs)
    top = ranked[:top_n]
    heat = {}
    for m in messages_flat:
        cid = str(m.get("channel_id") or "")
        heat[cid] = heat.get(cid, 0) + 1
    max_h = max(heat.values()) if heat else 1
    heatmap = [
        {"channel_id": k, "activity": v, "intensity": round(min(1.0, v / max_h), 3)}
        for k, v in sorted(heat.items(), key=lambda kv: kv[1], reverse=True)[:24]
    ]
    scores = [x.score for x in ranked[:15]]
    avg = sum(scores) / len(scores) if scores else 0.0
    health = int(max(0, min(100, round(100 - min(80, avg * 12)))))
    return {
        "ranked_messages": [
            {
                "channel_id": m.channel_id,
                "channel_name": m.channel_name,
                "ts": m.ts,
                "user_id": m.user_id,
                "text": m.text[:280],
                "score": round(m.score, 3),
                "reasons": m.reasons,
            }
            for m in top
        ],
        "heatmap": heatmap,
        "slack_health_score": health,
        "priority_keywords": prefs.priority_keywords,
    }


def build_unread_style_summary(
    *,
    settings: Settings,
    messages_flat: list[dict[str, Any]],
    channels_scanned: list[dict[str, Any]],
) -> dict[str, Any]:
    prefs = load_slack_channel_prefs(settings)
    ranked = rank_messages(messages_flat, prefs)
    by_ch: dict[str, list] = {}
    for m in ranked[:80]:
        by_ch.setdefault(m.channel_id, []).append(m)
    ch_meta = {c["id"]: c for c in channels_scanned}
    channels_out = []
    for cid, msgs in sorted(by_ch.items(), key=lambda kv: len(kv[1]), reverse=True)[:20]:
        meta = ch_meta.get(cid, {})
        channels_out.append(
            {
                "channel_id": cid,
                "name": meta.get("name"),
                "high_priority_hits": len(msgs),
                "top_snippet": msgs[0].text[:200] if msgs else "",
                "top_score": round(msgs[0].score, 2) if msgs else 0.0,
            }
        )
    return {
        "channels": channels_out,
        "note": "Heuristic inbox: recent messages scored by urgency signals (not Slack native unread).",
    }
