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
_MAX_TTL_S = 3600
_DEFAULT_APPLY_TTL_S = 600


def _signing_key(settings: Settings) -> bytes:
    if settings.system_patch_secret and settings.system_patch_secret.strip():
        return settings.system_patch_secret.strip().encode("utf-8")
    raw = (
        (settings.slack_client_secret or "")
        + "|"
        + (settings.slack_encryption_key or "")
        + "|jarvis-system-patch-v1"
    )
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _diff_fingerprint(diff_text: str) -> str:
    return hashlib.sha256(diff_text.encode("utf-8")).hexdigest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


@dataclass
class PatchApplyPayload:
    patch_id: str
    diff_sha256: str
    branch_name: str
    base_sha: str
    exp: int
    nonce: str


def mint_patch_apply_token(
    settings: Settings,
    *,
    patch_id: str,
    diff_text: str,
    branch_name: str,
    base_sha: str,
    ttl_s: int = _DEFAULT_APPLY_TTL_S,
) -> tuple[str, int]:
    ttl = max(60, min(_MAX_TTL_S, int(ttl_s)))
    now = int(time.time())
    exp = now + ttl
    nonce = secrets.token_hex(8)
    body = {
        "v": _TOKEN_VERSION,
        "act": "apply",
        "pid": patch_id.strip(),
        "h": _diff_fingerprint(diff_text),
        "branch": branch_name.strip(),
        "base": base_sha.strip(),
        "exp": exp,
        "n": nonce,
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_signing_key(settings), raw, hashlib.sha256).digest()
    token = _b64url(raw) + "." + _b64url(sig)
    return token, exp


def verify_patch_apply_token(settings: Settings, *, token: str, diff_text: str) -> PatchApplyPayload:
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
    if int(obj.get("v") or 0) != _TOKEN_VERSION or str(obj.get("act") or "") != "apply":
        raise ValueError("bad_version_or_action")
    exp = int(obj.get("exp") or 0)
    if exp < int(time.time()):
        raise ValueError("expired")
    h = str(obj.get("h") or "")
    if h != _diff_fingerprint(diff_text):
        raise ValueError("diff_mismatch")
    pid = str(obj.get("pid") or "").strip()
    branch = str(obj.get("branch") or "").strip()
    base = str(obj.get("base") or "").strip()
    if not pid or not branch or not base:
        raise ValueError("bad_payload_fields")
    return PatchApplyPayload(
        patch_id=pid,
        diff_sha256=h,
        branch_name=branch,
        base_sha=base,
        exp=exp,
        nonce=str(obj.get("n") or ""),
    )


@dataclass
class RollbackPayload:
    patch_id: str
    base_sha: str
    exp: int
    nonce: str


def mint_rollback_token(
    settings: Settings,
    *,
    patch_id: str,
    base_sha: str,
    ttl_s: int = _DEFAULT_APPLY_TTL_S,
) -> tuple[str, int]:
    ttl = max(60, min(_MAX_TTL_S, int(ttl_s)))
    now = int(time.time())
    exp = now + ttl
    nonce = secrets.token_hex(8)
    body = {
        "v": _TOKEN_VERSION,
        "act": "rollback",
        "pid": patch_id.strip(),
        "base": base_sha.strip(),
        "exp": exp,
        "n": nonce,
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_signing_key(settings), raw, hashlib.sha256).digest()
    token = _b64url(raw) + "." + _b64url(sig)
    return token, exp


def verify_rollback_token(settings: Settings, *, token: str, patch_id: str) -> RollbackPayload:
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
    if int(obj.get("v") or 0) != _TOKEN_VERSION or str(obj.get("act") or "") != "rollback":
        raise ValueError("bad_version_or_action")
    exp = int(obj.get("exp") or 0)
    if exp < int(time.time()):
        raise ValueError("expired")
    pid = str(obj.get("pid") or "").strip()
    base = str(obj.get("base") or "").strip()
    if not pid or pid != patch_id.strip():
        raise ValueError("patch_id_mismatch")
    if not base:
        raise ValueError("bad_payload_fields")
    return RollbackPayload(patch_id=pid, base_sha=base, exp=exp, nonce=str(obj.get("n") or ""))
