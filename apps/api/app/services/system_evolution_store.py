from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import aiosqlite

from app.core.config import Settings

logger = logging.getLogger(__name__)


class SystemEvolutionStore:
    """Local-first incident, audit, and patch proposal history."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db_path = settings.data_dir / "system" / "evolution.sqlite3"

    async def setup(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  severity TEXT NOT NULL,
                  subsystem TEXT,
                  summary TEXT NOT NULL,
                  detail_json TEXT NOT NULL DEFAULT '{}',
                  repair_output_json TEXT
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_runs (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  mode TEXT NOT NULL,
                  tools_json TEXT NOT NULL DEFAULT '{}',
                  synthesis_text TEXT NOT NULL DEFAULT '',
                  debt_score INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS patch_proposals (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL DEFAULT (datetime('now')),
                  status TEXT NOT NULL,
                  branch_name TEXT NOT NULL,
                  base_sha TEXT NOT NULL,
                  diff_sha256 TEXT NOT NULL,
                  diff_preview TEXT NOT NULL,
                  manifest_json TEXT,
                  backup_root TEXT,
                  outcome_text TEXT,
                  applied_at TEXT,
                  rolled_back_at TEXT
                );
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_audits_created ON audit_runs(created_at);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_patches_status ON patch_proposals(status);")
            await db.commit()
        logger.info("system evolution store at %s", self.db_path)

    async def insert_incident(
        self,
        *,
        severity: str,
        subsystem: str | None,
        summary: str,
        detail: dict[str, Any],
        repair_output: dict[str, Any] | None = None,
    ) -> str:
        iid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO incidents (id, severity, subsystem, summary, detail_json, repair_output_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    iid,
                    severity,
                    subsystem,
                    summary,
                    json.dumps(detail, separators=(",", ":")),
                    json.dumps(repair_output, separators=(",", ":")) if repair_output is not None else None,
                ),
            )
            await db.commit()
        return iid

    async def list_incidents(self, *, limit: int = 50) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, created_at, severity, subsystem, summary, detail_json, repair_output_json
                FROM incidents
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            detail: dict[str, Any] = {}
            repair = None
            try:
                detail = json.loads(r["detail_json"] or "{}")
            except json.JSONDecodeError:
                pass
            if r["repair_output_json"]:
                try:
                    repair = json.loads(r["repair_output_json"])
                except json.JSONDecodeError:
                    repair = None
            out.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "severity": r["severity"],
                    "subsystem": r["subsystem"],
                    "summary": r["summary"],
                    "detail": detail,
                    "repair_output": repair,
                }
            )
        return out

    async def insert_audit_run(
        self,
        *,
        mode: str,
        tools: dict[str, Any],
        synthesis: str,
        debt_score: int,
    ) -> str:
        aid = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO audit_runs (id, mode, tools_json, synthesis_text, debt_score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (aid, mode, json.dumps(tools, separators=(",", ":")), synthesis, int(debt_score)),
            )
            await db.commit()
        return aid

    async def list_audit_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, created_at, mode, tools_json, synthesis_text, debt_score
                FROM audit_runs
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            tools: dict[str, Any] = {}
            try:
                tools = json.loads(r["tools_json"] or "{}")
            except json.JSONDecodeError:
                pass
            out.append(
                {
                    "id": r["id"],
                    "created_at": r["created_at"],
                    "mode": r["mode"],
                    "tools": tools,
                    "synthesis": r["synthesis_text"],
                    "debt_score": r["debt_score"],
                }
            )
        return out

    async def insert_patch_proposal(
        self,
        *,
        proposal_id: str | None = None,
        status: str,
        branch_name: str,
        base_sha: str,
        diff_sha256: str,
        diff_preview: str,
    ) -> str:
        pid = proposal_id or str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO patch_proposals (id, status, branch_name, base_sha, diff_sha256, diff_preview)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (pid, status, branch_name, base_sha, diff_sha256, diff_preview[:16_000]),
            )
            await db.commit()
        return pid

    async def get_patch_proposal(self, patch_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM patch_proposals WHERE id = ?", (patch_id,))
            r = await cur.fetchone()
        if not r:
            return None
        manifest = None
        if r["manifest_json"]:
            try:
                manifest = json.loads(r["manifest_json"])
            except json.JSONDecodeError:
                manifest = None
        return {
            "id": r["id"],
            "created_at": r["created_at"],
            "status": r["status"],
            "branch_name": r["branch_name"],
            "base_sha": r["base_sha"],
            "diff_sha256": r["diff_sha256"],
            "diff_preview": r["diff_preview"],
            "manifest": manifest,
            "backup_root": r["backup_root"],
            "outcome_text": r["outcome_text"],
            "applied_at": r["applied_at"],
            "rolled_back_at": r["rolled_back_at"],
        }

    async def update_patch_proposal(
        self,
        patch_id: str,
        *,
        status: str | None = None,
        manifest_json: str | None = None,
        backup_root: str | None = None,
        outcome_text: str | None = None,
        applied_at: str | None = None,
        rolled_back_at: str | None = None,
    ) -> None:
        fields: list[str] = []
        vals: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            vals.append(status)
        if manifest_json is not None:
            fields.append("manifest_json = ?")
            vals.append(manifest_json)
        if backup_root is not None:
            fields.append("backup_root = ?")
            vals.append(backup_root)
        if outcome_text is not None:
            fields.append("outcome_text = ?")
            vals.append(outcome_text)
        if applied_at is not None:
            fields.append("applied_at = ?")
            vals.append(applied_at)
        if rolled_back_at is not None:
            fields.append("rolled_back_at = ?")
            vals.append(rolled_back_at)
        if not fields:
            return
        vals.append(patch_id)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"UPDATE patch_proposals SET {', '.join(fields)} WHERE id = ?", vals)
            await db.commit()

    async def list_patch_proposals(self, *, limit: int = 30) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT id, created_at, status, branch_name, base_sha, diff_sha256, outcome_text, applied_at, rolled_back_at
                FROM patch_proposals
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
