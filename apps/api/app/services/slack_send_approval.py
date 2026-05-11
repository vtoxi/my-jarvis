from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.config import Settings

_TOKEN_VERSION = 1
_MAX_TTL_S = 900
_DEFAULT_TTL_S = 300


def _signing_key(settings: Settings) -> bytes:
    if settings.slack_approval_secret and settings.slack_approval_secret.strip():
        return settings.slack_approval_secret.strip().encode("utf-8")
    raw = (
        (settings.slack_client_secret or "")
        + "|"
        + (settings.slack_encryption_key or "")
        + "|jarvis-slack-send-approval-v1"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


@dataclass
class SendApprovalPayload:
    channel_id: str
    thread_ts: str | None
    text_sha256: str
    exp: int
    nonce: str


def mint_send_approval_token(
    settings: Settings,
    *,
    channel_id: str,
    thread_ts: str | None,
    text: str,
    ttl_s: int = _DEFAULT_TTL_S,
) -> tuple[str, int]:
    ttl = max(30, min(_MAX_TTL_S, int(ttl_s)))
    now = int(time.time())
    exp = now + ttl
    nonce = secrets.token_hex(8)
    body = {
        "v": _TOKEN_VERSION,
        "cid": channel_id.strip(),
        "tts": (thread_ts.strip() if thread_ts else None) or None,
        "h": _text_fingerprint(text),
        "exp": exp,
        "n": nonce,
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_signing_key(settings), raw, hashlib.sha256).digest()
    token = _b64url(raw) + "." + _b64url(sig)
    return token, exp


def verify_send_approval_token(settings: Settings, *, token: str, text: str) -> SendApprovalPayload:
    parts = (token or "").strip().split(".", 1)
    if len(parts) != 2:
        raise ValueError("malformed_token")
    try:
        raw = _b64url_decode(parts[0])
        sig = _b64url_decode(parts[1])
    except (ValueError, OSError) as e:
        raise ValueError("malformed_token") from e
    expected = hmac.new(_signing_key(settings), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("bad_signature")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError("bad_payload") from e
    if int(obj.get("v") or 0) != _TOKEN_VERSION:
        raise ValueError("bad_version")
    exp = int(obj.get("exp") or 0)
    if exp < int(time.time()):
        raise ValueError("expired")
    h = str(obj.get("h") or "")
    if h != _text_fingerprint(text):
        raise ValueError("text_mismatch")
    cid = str(obj.get("cid") or "").strip()
    if not cid:
        raise ValueError("bad_channel")
    tts = obj.get("tts")
    tts_s = str(tts).strip() if tts else None
    return SendApprovalPayload(channel_id=cid, thread_ts=tts_s or None, text_sha256=h, exp=exp, nonce=str(obj.get("n") or ""))
