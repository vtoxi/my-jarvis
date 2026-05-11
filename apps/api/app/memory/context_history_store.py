from __future__ import annotations

import base64
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

logger = logging.getLogger(__name__)


def _fernet(settings: Settings) -> Fernet | None:
    if settings.screen_context_fernet_key:
        try:
            return Fernet(settings.screen_context_fernet_key.strip().encode("utf-8"))
        except Exception:
            return None
    key_path = settings.data_dir / "screen" / ".context_fernet_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        key = key_path.read_bytes()
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        logger.warning("Auto-generated screen context Fernet key at %s", key_path)
    return Fernet(key)


class ContextHistoryStore:
    def __init__(self, db_path: Path, settings: Settings) -> None:
        self.db_path = db_path
        self.settings = settings

    async def setup(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS context_snapshots (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  cipher BLOB,
                  plain_json TEXT
                );
                """
            )
            await db.commit()
        logger.info("context history store at %s", self.db_path)

    async def append_snapshot(
        self,
        *,
        front_app: str | None,
        window_title: str | None,
        ocr_excerpt: str,
        tags: list[str],
    ) -> None:
        payload: dict[str, Any] = {
            "front_app": front_app,
            "window_title": window_title,
            "ocr_excerpt": (ocr_excerpt or "")[:8000],
            "tags": tags,
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        use_enc = bool(self.settings.screen_context_history_encrypt)
        f = _fernet(self.settings) if use_enc else None
        if use_enc and f is not None:
            blob = f.encrypt(raw)
            plain = None
        else:
            blob = None
            plain = raw.decode("utf-8")

        sid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO context_snapshots (id, cipher, plain_json) VALUES (?, ?, ?)",
                (sid, blob, plain),
            )
            await db.commit()

    async def recent_plain(self, limit: int = 12) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        f = _fernet(self.settings) if self.settings.screen_context_history_encrypt else None
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT cipher, plain_json FROM context_snapshots ORDER BY datetime(created_at) DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
        for cipher_blob, plain_json in rows:
            if plain_json:
                try:
                    out.append(json.loads(plain_json))
                except json.JSONDecodeError:
                    continue
                continue
            if f is None or cipher_blob is None:
                continue
            try:
                raw = f.decrypt(cipher_blob)
                out.append(json.loads(raw.decode("utf-8")))
            except (InvalidToken, json.JSONDecodeError, ValueError):
                continue
        return out
