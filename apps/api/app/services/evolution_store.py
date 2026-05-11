from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import aiosqlite
import numpy as np

from app.core.config import Settings
from app.schemas.evolution import TwinProfilePayload

logger = logging.getLogger(__name__)

_DEFAULT_TWIN: dict[str, Any] = {
    "workflow": {},
    "decision": {},
    "communication": {"formality": "neutral", "brevity": "medium"},
    "focus": {},
    "strategy": {},
    "meta": {
        "confidence_by_dimension": {
            "workflow": 0.15,
            "decision": 0.15,
            "communication": 0.25,
            "focus": 0.15,
            "strategy": 0.15,
        },
        "notes": "Initial profile — correct via PATCH /evolution/twin",
    },
}


class EvolutionStore:
    """Phase 8 — twin profile, idle runs, audit log, pending approvals (local SQLite)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db_path = settings.data_dir / "evolution" / "phase8.sqlite3"

    async def setup(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS twin_current (
                  id INTEGER PRIMARY KEY CHECK (id = 1),
                  version INTEGER NOT NULL DEFAULT 1,
                  payload_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS twin_history (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  version INTEGER NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS idle_runs (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  report_markdown TEXT NOT NULL,
                  metrics_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS evolution_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  kind TEXT NOT NULL,
                  payload_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_changes (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  kind TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending'
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS kg_chunks (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  source TEXT NOT NULL,
                  text TEXT NOT NULL,
                  embedding_json TEXT NOT NULL,
                  meta_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_kg_created ON kg_chunks(created_at);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_kg_source ON kg_chunks(source);")
            await db.commit()
        await self._ensure_twin_row()
        logger.info("evolution store at %s", self.db_path)

    async def _ensure_twin_row(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM twin_current WHERE id = 1")
            row = await cur.fetchone()
            if row and row[0]:
                return
            await db.execute(
                "INSERT INTO twin_current (id, version, payload_json) VALUES (1, 1, ?)",
                (json.dumps(_DEFAULT_TWIN, separators=(",", ":")),),
            )
            await db.commit()

    async def get_twin(self) -> tuple[int, dict[str, Any], str | None]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT version, payload_json, updated_at FROM twin_current WHERE id = 1")
            r = await cur.fetchone()
        if not r:
            return 1, dict(_DEFAULT_TWIN), None
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = dict(_DEFAULT_TWIN)
        return int(r["version"]), payload, str(r["updated_at"]) if r["updated_at"] else None

    async def update_twin(self, profile: TwinProfilePayload) -> tuple[int, str | None]:
        new_payload = profile.model_dump()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT version, payload_json FROM twin_current WHERE id = 1")
            r = await cur.fetchone()
            old_v = int(r[0]) if r else 1
            old_json = str(r[1]) if r else json.dumps(_DEFAULT_TWIN)
            new_v = old_v + 1
            await db.execute(
                "INSERT INTO twin_history (version, payload_json) VALUES (?, ?)",
                (old_v, old_json),
            )
            await db.execute(
                """
                UPDATE twin_current SET version = ?, payload_json = ?, updated_at = datetime('now') WHERE id = 1
                """,
                (new_v, json.dumps(new_payload, separators=(",", ":"))),
            )
            await db.commit()
            cur2 = await db.execute("SELECT updated_at FROM twin_current WHERE id = 1")
            u = await cur2.fetchone()
        return new_v, str(u[0]) if u else None

    async def rollback_twin(self, steps: int) -> tuple[bool, int, str]:
        last_msg = "no history"
        last_ver = 1
        applied = 0
        for _ in range(int(steps)):
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT id, version, payload_json FROM twin_history ORDER BY id DESC LIMIT 1",
                )
                r = await cur.fetchone()
                if not r:
                    return applied > 0, last_ver, last_msg if applied else "no history to rollback"
                hid = int(r["id"])
                last_ver = int(r["version"])
                payload = str(r["payload_json"])
                await db.execute(
                    "UPDATE twin_current SET version = ?, payload_json = ?, updated_at = datetime('now') WHERE id = 1",
                    (last_ver, payload),
                )
                await db.execute("DELETE FROM twin_history WHERE id = ?", (hid,))
                await db.commit()
                applied += 1
                last_msg = f"restored step {applied} to version {last_ver}"
        return True, last_ver, last_msg

    async def append_idle_run(self, *, report: str, metrics: dict[str, Any]) -> str:
        rid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO idle_runs (id, report_markdown, metrics_json) VALUES (?, ?, ?)",
                (rid, report[:120_000], json.dumps(metrics, separators=(",", ":"))),
            )
            await db.commit()
        return rid

    async def last_idle_run(self) -> tuple[str | None, str | None]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, created_at FROM idle_runs ORDER BY datetime(created_at) DESC LIMIT 1",
            )
            r = await cur.fetchone()
        if not r:
            return None, None
        return str(r["id"]), str(r["created_at"])

    async def count_idle_runs(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM idle_runs")
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def append_event(self, *, kind: str, payload: dict[str, Any]) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO evolution_events (kind, payload_json) VALUES (?, ?)",
                (kind, json.dumps(payload, separators=(",", ":"))),
            )
            await db.commit()
            cur = await db.execute("SELECT last_insert_rowid()")
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def list_events(self, *, limit: int = 80) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, created_at, kind, payload_json FROM evolution_events
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
        out = []
        for r in rows:
            try:
                p = json.loads(r["payload_json"] or "{}")
            except json.JSONDecodeError:
                p = {}
            out.append({"id": r["id"], "created_at": r["created_at"], "kind": r["kind"], "payload": p})
        return out

    async def count_events_since(self, hours: int = 24) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                SELECT COUNT(*) FROM evolution_events
                WHERE datetime(created_at) > datetime('now', ?)
                """,
                (f"-{int(hours)} hours",),
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def insert_pending(self, *, kind: str, payload: dict[str, Any]) -> str:
        pid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO pending_changes (id, kind, payload_json, status) VALUES (?, ?, ?, 'pending')",
                (pid, kind, json.dumps(payload, separators=(",", ":"))),
            )
            await db.commit()
        return pid

    async def count_pending(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM pending_changes WHERE status = 'pending'")
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_pending(self, pending_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM pending_changes WHERE id = ?", (pending_id,))
            r = await cur.fetchone()
        if not r:
            return None
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        return {"id": r["id"], "kind": r["kind"], "status": r["status"], "payload": payload}

    async def mark_pending(self, pending_id: str, status: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE pending_changes SET status = ? WHERE id = ?", (status, pending_id))
            await db.commit()

    async def list_pending(self, *, limit: int = 50) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, created_at, kind, status, payload_json FROM pending_changes
                WHERE status = 'pending'
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
        out = []
        for r in rows:
            try:
                p = json.loads(r["payload_json"] or "{}")
            except json.JSONDecodeError:
                p = {}
            out.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "kind": r["kind"],
                    "status": r["status"],
                    "payload": p,
                }
            )
        return out

    async def kg_insert(
        self,
        *,
        source: str,
        text: str,
        embedding: list[float],
        meta: dict[str, Any] | None = None,
    ) -> str:
        cid = str(uuid.uuid4())
        meta = meta or {}
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO kg_chunks (id, source, text, embedding_json, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    source[:200],
                    text[:24_000],
                    json.dumps(embedding, separators=(",", ":")),
                    json.dumps(meta, separators=(",", ":")),
                ),
            )
            await db.commit()
        return cid

    async def kg_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM kg_chunks")
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def kg_last_created(self) -> str | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT created_at FROM kg_chunks ORDER BY id DESC LIMIT 1")
            r = await cur.fetchone()
        return str(r["created_at"]) if r else None

    async def kg_search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 8,
        max_rows: int = 800,
    ) -> list[dict[str, Any]]:
        if not query_embedding:
            return []
        q = np.asarray(query_embedding, dtype=np.float64)
        nq = float(np.linalg.norm(q))
        if nq < 1e-12:
            return []
        q = q / nq
        lim = max(50, min(5000, int(max_rows)))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, created_at, source, text, embedding_json, meta_json FROM kg_chunks
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?
                """,
                (lim,),
            )
            rows = await cur.fetchall()
        scored: list[tuple[float, dict[str, Any]]] = []
        for r in rows:
            try:
                emb = json.loads(r["embedding_json"] or "[]")
            except json.JSONDecodeError:
                continue
            if not isinstance(emb, list) or len(emb) != len(query_embedding):
                continue
            v = np.asarray(emb, dtype=np.float64)
            nv = float(np.linalg.norm(v))
            if nv < 1e-12:
                continue
            v = v / nv
            sim = float(np.dot(v, q))
            try:
                meta = json.loads(r["meta_json"] or "{}")
            except json.JSONDecodeError:
                meta = {}
            scored.append(
                (
                    sim,
                    {
                        "id": str(r["id"]),
                        "created_at": str(r["created_at"]),
                        "source": str(r["source"]),
                        "text": str(r["text"])[:2000],
                        "score": sim,
                        "meta": meta if isinstance(meta, dict) else {},
                    },
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[: max(1, min(50, int(top_k)))]]
