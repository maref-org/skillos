"""AgentCard — Agent 注册与发现

AgentCard 是 Men0 协议的核心数据结构，定义 Agent 的身份、能力和通信端点。
AgentRegistry 提供本地 SQLite 持久化注册表，支持注册、发现、心跳和超时摘除。

Usage:
    registry = AgentRegistry()
    card = AgentCard(agent_id="agent-001", name="Demo", capabilities=["research"])
    registry.register(card)
    registry.heartbeat("agent-001")
    agents = registry.discover(capability="research")
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillos.kernel.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_DB_PATH = "data/agent_registry.db"
_DEFAULT_HEARTBEAT_TIMEOUT = 300


AgentStatus = str  # "active" | "inactive" | "suspended"


@dataclass
class AgentCard:
    agent_id: str
    name: str
    version: str = "1.0.0"
    capabilities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    endpoint: str = ""
    public_key: str = ""
    status: AgentStatus = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCard:
        data = dict(data)
        data["capabilities"] = json.loads(data.get("capabilities", "[]"))
        data["skills"] = json.loads(data.get("skills", "[]"))
        data["metadata"] = json.loads(data.get("metadata", "{}"))
        return cls(**data)


class AgentRegistry:
    """本地 Agent 注册表（SQLite 持久化）"""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._cache: dict[str, AgentCard] = {}

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_cards (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL DEFAULT '1.0.0',
                    capabilities TEXT NOT NULL DEFAULT '[]',
                    skills TEXT NOT NULL DEFAULT '[]',
                    endpoint TEXT NOT NULL DEFAULT '',
                    public_key TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    registered_at REAL NOT NULL,
                    last_heartbeat REAL NOT NULL
                )
            """)

    def register(self, card: AgentCard) -> None:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO agent_cards
                (agent_id, name, version, capabilities, skills, endpoint,
                 public_key, status, metadata, registered_at, last_heartbeat)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    card.agent_id,
                    card.name,
                    card.version,
                    json.dumps(card.capabilities),
                    json.dumps(card.skills),
                    card.endpoint,
                    card.public_key,
                    card.status,
                    json.dumps(card.metadata),
                    now,
                    now,
                ),
            )
        self._cache[card.agent_id] = card
        logger.info("Agent registered: %s (%s)", card.agent_id, card.name)

    def discover(
        self,
        capability: str | None = None,
        skill: str | None = None,
        status: AgentStatus | None = "active",
    ) -> list[AgentCard]:
        with self._get_conn() as conn:
            conditions: list[str] = []
            params: list[Any] = []

            if status is not None:
                conditions.append("status = ?")
                params.append(status)

            rows = conn.execute(
                f"SELECT * FROM agent_cards{' WHERE ' + ' AND '.join(conditions) if conditions else ''}",  # nosec B608
                params,
            ).fetchall()

            results: list[AgentCard] = []
            for row in rows:
                card = AgentCard.from_dict(dict(row))
                if capability and capability not in card.capabilities:
                    continue
                if skill and skill not in card.skills:
                    continue
                results.append(card)

            return results

    def get_agent(self, agent_id: str) -> AgentCard | None:
        if agent_id in self._cache:
            return self._cache[agent_id]
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM agent_cards WHERE agent_id = ?", (agent_id,)).fetchone()
            if row is None:
                return None
            card = AgentCard.from_dict(dict(row))
            self._cache[agent_id] = card
            return card

    def heartbeat(self, agent_id: str) -> bool:
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE agent_cards SET last_heartbeat = ? WHERE agent_id = ?",
                (now, agent_id),
            )
            if cursor.rowcount == 0:
                return False
        if agent_id in self._cache:
            self._cache[agent_id].last_heartbeat = now
        return True

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE agent_cards SET status = ? WHERE agent_id = ?",
                (status, agent_id),
            )
            if cursor.rowcount == 0:
                return False
        if agent_id in self._cache:
            self._cache[agent_id].status = status
        logger.info("Agent %s status updated to %s", agent_id, status)
        return True

    def prune_inactive(self, timeout_seconds: int = _DEFAULT_HEARTBEAT_TIMEOUT) -> int:
        cutoff = time.time() - timeout_seconds
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE agent_cards SET status = 'inactive' WHERE status = 'active' AND last_heartbeat < ?",
                (cutoff,),
            )
        count = cursor.rowcount
        stale = [aid for aid, c in self._cache.items() if c.status == "active" and c.last_heartbeat < cutoff]
        for aid in stale:
            self._cache[aid].status = "inactive"
        if count > 0:
            logger.info("Pruned %d inactive agents (timeout=%ds)", count, timeout_seconds)
        return count

    def unregister(self, agent_id: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM agent_cards WHERE agent_id = ?", (agent_id,))
        self._cache.pop(agent_id, None)
        return cursor.rowcount > 0

    def count(self, status: AgentStatus | None = None) -> int:
        if status is None:
            with self._get_conn() as conn:
                return conn.execute("SELECT COUNT(*) FROM agent_cards").fetchone()[0]
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM agent_cards WHERE status = ?", (status,)).fetchone()[0]

    def get_stats(self) -> dict[str, Any]:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM agent_cards").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM agent_cards WHERE status = 'active'").fetchone()[0]
            inactive = conn.execute("SELECT COUNT(*) FROM agent_cards WHERE status = 'inactive'").fetchone()[0]
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "suspended": total - active - inactive,
        }
