from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.config import Settings

_V = 1
_MAX_TTL = 3600


def _key(settings: Settings) -> bytes:
    raw = (
        (settings.system_patch_secret or "")
        + "|"
        + (settings.slack_client_secret or "")
        + "|jarvis-evolution-learn-approve-v1"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


@dataclass
class LearnApprovePayload:
    pending_id: str
    exp: int


def mint_learn_approval_token(settings: Settings, *, pending_id: str, ttl_s: int = 900) -> tuple[str, int]:
    ttl = max(60, min(_MAX_TTL, int(ttl_s)))
    exp = int(time.time()) + ttl
    nonce = secrets.token_hex(8)
    body = {"v": _V, "pid": pending_id.strip(), "exp": exp, "n": nonce}
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_key(settings), raw, hashlib.sha256).digest()
    return _b64url(raw) + "." + _b64url(sig), exp


def verify_learn_approval_token(settings: Settings, *, token: str, pending_id: str) -> LearnApprovePayload:
    parts = (token or "").strip().split(".", 1)
    if len(parts) != 2:
        raise ValueError("malformed_token")
    raw = _b64url_decode(parts[0])
    sig = _b64url_decode(parts[1])
    expected = hmac.new(_key(settings), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("bad_signature")
    obj = json.loads(raw.decode("utf-8"))
    if int(obj.get("v") or 0) != _V:
        raise ValueError("bad_version")
    exp = int(obj.get("exp") or 0)
    if exp < int(time.time()):
        raise ValueError("expired")
    pid = str(obj.get("pid") or "").strip()
    if not pid or pid != pending_id.strip():
        raise ValueError("pending_id_mismatch")
    return LearnApprovePayload(pending_id=pid, exp=exp)
