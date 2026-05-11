from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.slack import SlackChannelPrefs

MENTION_RE = re.compile(r"<@[A-Z0-9]+>")
HERE_RE = re.compile(r"<!here>|<!channel>", re.IGNORECASE)


@dataclass
class ScoredSlackMessage:
    channel_id: str
    channel_name: str | None
    ts: str
    user_id: str | None
    text: str
    score: float
    reasons: list[str]


def _keyword_hits(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    t = (text or "").lower()
    hits: list[str] = []
    for kw in keywords:
        k = (kw or "").strip().lower()
        if not k:
            continue
        if k in t:
            hits.append(kw)
    return len(hits), hits


def score_message(
    *,
    text: str,
    user_id: str | None,
    channel_id: str,
    channel_name: str | None,
    prefs: SlackChannelPrefs,
    channel_importance: float,
    channel_message_volume: int,
) -> tuple[float, list[str]]:
    score = 0.15
    reasons: list[str] = []

    if channel_id in prefs.priority_channel_ids:
        score += 1.1
        reasons.append("priority_channel")

    score += min(1.25, float(channel_importance))

    if user_id and user_id in prefs.vip_user_ids:
        score += 1.6
        reasons.append("vip_sender")

    n_kw, kws = _keyword_hits(text, prefs.priority_keywords)
    if n_kw:
        bump = min(2.0, 0.45 * n_kw)
        score += bump
        reasons.append(f"keywords:{','.join(kws[:6])}")

    if MENTION_RE.search(text or ""):
        score += 0.85
        reasons.append("user_mention_token")

    if HERE_RE.search(text or ""):
        score += 1.1
        reasons.append("broadcast_here_channel")

    vol = max(0, int(channel_message_volume))
    score += min(0.9, 0.02 * vol)
    if vol >= 12:
        reasons.append("high_channel_volume")

    return score, reasons


def rank_messages(
    rows: list[dict[str, str | int | float | None]],
    prefs: SlackChannelPrefs,
    *,
    default_channel_importance: float = 0.55,
) -> list[ScoredSlackMessage]:
    out: list[ScoredSlackMessage] = []
    for r in rows:
        cid = str(r.get("channel_id") or "")
        if not cid:
            continue
        ch_name = r.get("channel_name")
        ch_name_s = str(ch_name) if ch_name is not None else None
        imp = float(r.get("channel_importance") or default_channel_importance)
        vol = int(r.get("channel_message_volume") or 0)
        text = str(r.get("text") or "")
        uid = r.get("user_id")
        uid_s = str(uid) if uid is not None else None
        ts = str(r.get("ts") or "")
        s, reasons = score_message(
            text=text,
            user_id=uid_s,
            channel_id=cid,
            channel_name=ch_name_s,
            prefs=prefs,
            channel_importance=imp,
            channel_message_volume=vol,
        )
        out.append(
            ScoredSlackMessage(
                channel_id=cid,
                channel_name=ch_name_s,
                ts=ts,
                user_id=uid_s,
                text=text,
                score=s,
                reasons=reasons,
            )
        )
    out.sort(key=lambda m: m.score, reverse=True)
    return out
