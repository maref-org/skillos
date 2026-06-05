#!/usr/bin/env python3
"""State Persistor — 跨会话状态持久化存储

职责:
  - 会话状态持久化 (key-value)
  - 任务执行结果记忆
  - TTL 过期机制
  - 跨会话状态查询
"""

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = "data/skillos_state.db"


@dataclass
class PersistentState:
    session_id: str
    state_key: str
    state_value: Any
    created_at: str = ""
    updated_at: str = ""
    ttl_seconds: int = 0


@dataclass
class TaskMemory:
    task_id: str
    session_id: str
    context: dict
    status: str = "pending"
    result: dict | None = None
    created_at: str = ""
    completed_at: str = ""


class StatePersistor:
    """跨会话状态持久化存储"""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_states (
                    session_id TEXT NOT NULL,
                    state_key TEXT NOT NULL,
                    state_value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    ttl_seconds INTEGER DEFAULT 0,
                    PRIMARY KEY (session_id, state_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_memory (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    context TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_session
                ON task_memory(session_id)
            """)

    def save_state(self, state: PersistentState) -> bool:
        """保存会话状态"""
        now = datetime.now().isoformat()
        created = state.created_at or now
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO session_states
                    (session_id, state_key, state_value, created_at, updated_at, ttl_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        state.session_id,
                        state.state_key,
                        json.dumps(state.state_value),
                        created,
                        now,
                        state.ttl_seconds,
                    ),
                )
            logger.debug("State saved: %s/%s", state.session_id, state.state_key)
            return True
        except Exception as e:
            logger.error("Failed to save state: %s", e)
            return False

    def load_state(self, session_id: str, state_key: str) -> Any | None:
        """加载会话状态"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT state_value, ttl_seconds, updated_at FROM session_states WHERE session_id=? AND state_key=?",
                (session_id, state_key),
            )
            row = cursor.fetchone()
            if not row:
                return None

            state_value = json.loads(row["state_value"])
            ttl = row["ttl_seconds"]

            if ttl > 0:
                updated_at = datetime.fromisoformat(row["updated_at"])
                if (datetime.now() - updated_at).total_seconds() > ttl:
                    conn.execute(
                        "DELETE FROM session_states WHERE session_id=? AND state_key=?",
                        (session_id, state_key),
                    )
                    return None

            return state_value

    def delete_state(self, session_id: str, state_key: str) -> bool:
        """删除会话状态"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM session_states WHERE session_id=? AND state_key=?",
                (session_id, state_key),
            )
            return cursor.rowcount > 0

    def list_states(self, session_id: str) -> list[dict]:
        """列出会话所有状态键"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT state_key, updated_at, ttl_seconds FROM session_states WHERE session_id=? ORDER BY updated_at DESC",
                (session_id,),
            )
            return [
                {
                    "key": row["state_key"],
                    "updated_at": row["updated_at"],
                    "ttl_seconds": row["ttl_seconds"],
                }
                for row in cursor.fetchall()
            ]

    def save_task_result(
        self,
        task_id: str,
        session_id: str,
        result: dict,
        context: dict,
        status: str = "completed",
    ) -> bool:
        """保存任务执行结果到 memory"""
        now = datetime.now().isoformat()
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO task_memory
                    (task_id, session_id, context, status, result, created_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        session_id,
                        json.dumps(context),
                        status,
                        json.dumps(result) if result else None,
                        now,
                        now if status == "completed" else None,
                    ),
                )
            logger.debug("Task result saved: %s", task_id)
            return True
        except Exception as e:
            logger.error("Failed to save task result: %s", e)
            return False

    def get_task_history(self, session_id: str, limit: int = 10) -> list[dict]:
        """获取会话任务历史"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """SELECT task_id, context, status, result, created_at, completed_at
                FROM task_memory WHERE session_id=?
                ORDER BY created_at DESC LIMIT ?""",
                (session_id, limit),
            )
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "task_id": row["task_id"],
                        "context": json.loads(row["context"]),
                        "status": row["status"],
                        "result": json.loads(row["result"]) if row["result"] else None,
                        "created_at": row["created_at"],
                        "completed_at": row["completed_at"],
                    }
                )
            return results

    def get_task_by_id(self, task_id: str) -> dict | None:
        """根据 task_id 查询任务"""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM task_memory WHERE task_id=?",
                (task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "task_id": row["task_id"],
                "session_id": row["session_id"],
                "context": json.loads(row["context"]),
                "status": row["status"],
                "result": json.loads(row["result"]) if row["result"] else None,
                "created_at": row["created_at"],
                "completed_at": row["completed_at"],
            }

    def cleanup_expired(self) -> int:
        """清理过期状态"""
        now = datetime.now()
        count = 0
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT session_id, state_key, ttl_seconds, updated_at FROM session_states WHERE ttl_seconds > 0"
            )
            for row in cursor.fetchall():
                updated_at = datetime.fromisoformat(row["updated_at"])
                if (now - updated_at).total_seconds() > row["ttl_seconds"]:
                    conn.execute(
                        "DELETE FROM session_states WHERE session_id=? AND state_key=?",
                        (row["session_id"], row["state_key"]),
                    )
                    count += 1
        if count > 0:
            logger.info("Cleaned up %d expired states", count)
        return count

    def get_stats(self) -> dict:
        """获取存储统计"""
        with self._get_conn() as conn:
            state_count = conn.execute("SELECT COUNT(*) FROM session_states").fetchone()[0]
            task_count = conn.execute("SELECT COUNT(*) FROM task_memory").fetchone()[0]
            session_count = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM session_states"
            ).fetchone()[0]
            return {
                "total_states": state_count,
                "total_tasks": task_count,
                "total_sessions": session_count,
            }
