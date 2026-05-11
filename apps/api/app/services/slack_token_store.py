from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

logger = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_NAME = "oauth_store.json"


@dataclass
class SlackCredentials:
    access_token: str
    team_id: str
    team_name: str | None
    bot_user_id: str | None


def _slack_dir(settings: Settings) -> Path:
    d = settings.data_dir / "slack"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fernet(settings: Settings) -> Fernet:
    if settings.slack_encryption_key:
        key = settings.slack_encryption_key.strip().encode("utf-8")
    else:
        key_path = _slack_dir(settings) / ".fernet_key"
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass
            logger.warning(
                "Slack token encryption key auto-generated at %s — set JARVIS_SLACK_ENCRYPTION_KEY for production.",
                key_path,
            )
    return Fernet(key)


def _store_path(settings: Settings) -> Path:
    return _slack_dir(settings) / STORE_NAME


def save_credentials(settings: Settings, payload: dict[str, Any]) -> None:
    f = _fernet(settings)
    blob = f.encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    out = {"v": STORE_VERSION, "data": base64.b64encode(blob).decode("ascii")}
    path = _store_path(settings)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_credentials(settings: Settings) -> SlackCredentials | None:
    path = _store_path(settings)
    if not path.exists():
        return None
    try:
        outer = json.loads(path.read_text(encoding="utf-8"))
        if outer.get("v") != STORE_VERSION or "data" not in outer:
            return None
        raw = base64.b64decode(str(outer["data"]).encode("ascii"))
        f = _fernet(settings)
        inner = json.loads(f.decrypt(raw).decode("utf-8"))
    except (json.JSONDecodeError, InvalidToken, OSError, ValueError) as e:
        logger.warning("slack credential load failed: %s", e)
        return None

    token = str(inner.get("access_token") or "").strip()
    team_id = str(inner.get("team_id") or "").strip()
    if not token or not team_id:
        return None
    return SlackCredentials(
        access_token=token,
        team_id=team_id,
        team_name=(str(inner["team_name"]).strip() if inner.get("team_name") else None),
        bot_user_id=(str(inner["bot_user_id"]).strip() if inner.get("bot_user_id") else None),
    )


def clear_credentials(settings: Settings) -> None:
    path = _store_path(settings)
    if path.exists():
        path.unlink()
