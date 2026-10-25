"""
SQLite database layer for content calendar.
"""

import json
import logging
import os
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS calendar_entries (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL DEFAULT 'general',
    source_content_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    platform_variants TEXT DEFAULT '{}',
    scheduled_at TEXT DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    published_ids TEXT DEFAULT '{}',
    metrics TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calendar_status ON calendar_entries(status);
CREATE INDEX IF NOT EXISTS idx_calendar_source ON calendar_entries(source_content_id);
CREATE INDEX IF NOT EXISTS idx_calendar_created ON calendar_entries(created_at);
"""


class CalendarDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path

    def init(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(SCHEMA_SQL)
        except Exception as e:
            logger.error(f"CalendarDB init failed: {e}")

    def upsert(self, entry) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO calendar_entries
                    (id, content_type, source_content_id, title,
                     platform_variants, scheduled_at, status,
                     published_ids, metrics, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry.id,
                        entry.content_type,
                        entry.source_content_id,
                        entry.title,
                        json.dumps(entry.platform_variants, ensure_ascii=False),
                        json.dumps(entry.scheduled_at, ensure_ascii=False),
                        entry.status,
                        json.dumps(entry.published_ids, ensure_ascii=False),
                        json.dumps(entry.metrics, ensure_ascii=False),
                        entry.created_at,
                        entry.updated_at,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"CalendarDB upsert failed: {e}")
            return False

    def get(self, entry_id: str) -> dict[str, Any] | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT * FROM calendar_entries WHERE id = ?", (entry_id,)).fetchone()
            if row:
                return self._row_to_dict(row)
        except Exception:
            pass
        return None

    def list_by_status(self, status: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM calendar_entries WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception:
            return []

    def update_status(self, entry_id: str, status: str, published_ids: dict | None = None) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                if published_ids:
                    conn.execute(
                        """UPDATE calendar_entries SET status = ?,
                        published_ids = ?, updated_at = datetime('now')
                        WHERE id = ?""",
                        (status, json.dumps(published_ids, ensure_ascii=False), entry_id),
                    )
                else:
                    conn.execute(
                        """UPDATE calendar_entries SET status = ?,
                        updated_at = datetime('now') WHERE id = ?""",
                        (status, entry_id),
                    )
            return True
        except Exception:
            return False

    def count_today(self, platform: str) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """SELECT COUNT(*) FROM calendar_entries
                    WHERE scheduled_at LIKE '%' || ? || '%'
                    AND date(updated_at) = date('now')""",
                    (platform,),
                ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        cols = [
            "id",
            "content_type",
            "source_content_id",
            "title",
            "platform_variants",
            "scheduled_at",
            "status",
            "published_ids",
            "metrics",
            "created_at",
            "updated_at",
        ]
        d = dict(zip(cols, row))
        for key in ("platform_variants", "scheduled_at", "published_ids", "metrics"):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = {}
        return d
