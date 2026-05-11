from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


class MemoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    async def setup(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                  id TEXT PRIMARY KEY,
                  session_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_store (
                  k TEXT PRIMARY KEY,
                  v TEXT NOT NULL,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """,
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_events (
                  id TEXT PRIMARY KEY,
                  agent_id TEXT NOT NULL,
                  session_id TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """,
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);")
            await db.commit()
        logger.info("memory store ready at %s", self.db_path)

    async def append_message(self, session_id: str, role: str, content: str) -> ChatMessage:
        mid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (id, session_id, role, content) VALUES (?, ?, ?, ?)",
                (mid, session_id, role, content),
            )
            await db.commit()
            cur = await db.execute(
                "SELECT id, session_id, role, content, created_at FROM messages WHERE id = ?",
                (mid,),
            )
            row = await cur.fetchone()
        if not row:
            raise RuntimeError("failed to read inserted message")
        return ChatMessage(id=row[0], session_id=row[1], role=row[2], content=row[3], created_at=row[4])

    async def list_messages(self, session_id: str, limit: int = 80) -> list[ChatMessage]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT id, session_id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY datetime(created_at) ASC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = await cur.fetchall()
        return [ChatMessage(id=r[0], session_id=r[1], role=r[2], content=r[3], created_at=r[4]) for r in rows]

    async def format_context(self, session_id: str, limit: int = 16) -> str:
        msgs = await self.list_messages(session_id, limit=limit)
        if not msgs:
            return "(no prior session messages)"
        tail = msgs[-limit:]
        lines = [f"- {m.role.upper()}: {m.content}" for m in tail]
        return "\n".join(lines)

    async def kv_get(self, key: str) -> Any | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT v FROM kv_store WHERE k = ?", (key,))
            row = await cur.fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return row[0]

    async def kv_set(self, key: str, value: Any) -> None:
        payload = json.dumps(value) if not isinstance(value, str) else value
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO kv_store (k, v) VALUES (?, ?)
                ON CONFLICT(k) DO UPDATE SET v = excluded.v, updated_at = datetime('now')
                """,
                (key, payload),
            )
            await db.commit()

    async def log_agent_event(self, agent_id: str, session_id: str, summary: str) -> None:
        eid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO agent_events (id, agent_id, session_id, summary) VALUES (?, ?, ?, ?)",
                (eid, agent_id, session_id, summary[:2000]),
            )
            await db.commit()

    async def last_event_for_agent(self, agent_id: str, session_id: str | None = None) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            if session_id:
                cur = await db.execute(
                    """
                    SELECT agent_id, summary, created_at
                    FROM agent_events
                    WHERE agent_id = ? AND session_id = ?
                    ORDER BY datetime(created_at) DESC
                    LIMIT 1
                    """,
                    (agent_id, session_id),
                )
            else:
                cur = await db.execute(
                    """
                    SELECT agent_id, summary, created_at
                    FROM agent_events
                    WHERE agent_id = ?
                    ORDER BY datetime(created_at) DESC
                    LIMIT 1
                    """,
                    (agent_id,),
                )
            row = await cur.fetchone()
        if not row:
            return None
        return {"agent_id": row[0], "summary": row[1], "created_at": row[2]}
