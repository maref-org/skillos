"""Reward logger — records (task, doc, outcome) triples for RL training.

Layer 2 of the RL-optimized document selection system.
Each entry logs which documents an agent read and whether the task succeeded.

Usage:
    from skillos.retrieval.reward_logger import RewardLogger

    logger = RewardLogger()
    logger.log_task_start(task_id="task-001", task_type="audit", tags=["meta"])
    logger.log_doc_read(task_id="task-001", doc_path="audit_docs/report.md")
    logger.log_task_outcome(task_id="task-001", success=True, details={})
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from skillos.audit import AuditEventType, log_audit

_LOG_DIR = Path("data")
_LOG_FILE = _LOG_DIR / "reward_logs.jsonl"


class RewardLogger:
    def __init__(self, log_path: str | Path | None = None):
        self._path = Path(log_path or _LOG_FILE)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._active_tasks: dict[str, dict[str, Any]] = {}

    def log_task_start(
        self,
        task_id: str,
        task_type: str,
        tags: list[str] | None = None,
        agent_id: str = "",
    ) -> None:
        record = {
            "event": "task_start",
            "task_id": task_id,
            "task_type": task_type,
            "tags": tags or [],
            "agent_id": agent_id,
            "timestamp": time.time(),
        }
        self._append(record)
        self._active_tasks[task_id] = {
            "task_type": task_type,
            "tags": tags or [],
            "docs_read": [],
            "start_time": time.time(),
            "agent_id": agent_id,
        }

    def log_doc_read(self, task_id: str, doc_path: str) -> None:
        record = {
            "event": "doc_read",
            "task_id": task_id,
            "doc_path": doc_path,
            "timestamp": time.time(),
        }
        self._append(record)
        if task_id in self._active_tasks:
            self._active_tasks[task_id]["docs_read"].append(doc_path)

    def log_task_outcome(
        self,
        task_id: str,
        success: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        task = self._active_tasks.pop(task_id, {})
        duration = time.time() - task.get("start_time", time.time())
        docs_count = len(task.get("docs_read", []))

        agent_id = task.get("agent_id", "system")
        reward = self.compute_reward(
            {
                "success": success,
                "docs_count": docs_count,
            }
        )
        record = {
            "event": "task_outcome",
            "task_id": task_id,
            "task_type": task.get("task_type", ""),
            "tags": task.get("tags", []),
            "success": success,
            "reward": reward,
            "docs_read": task.get("docs_read", []),
            "docs_count": docs_count,
            "duration_seconds": round(duration, 2),
            "details": details or {},
            "timestamp": time.time(),
            "agent_id": agent_id,
        }
        self._append(record)
        log_audit(
            AuditEventType.SKILL_EXECUTED,
            actor_id=agent_id,
            resource_id=task_id,
            action="retrieval_task_outcome",
            details={
                "task_type": task.get("task_type", ""),
                "success": success,
                "reward": reward,
                "docs_count": docs_count,
            },
        )

    def _append(self, record: dict[str, Any]) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def query(
        self,
        task_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        results: list[dict[str, Any]] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    if len(results) >= limit:
                        break
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if task_type and record.get("task_type") != task_type:
                        continue
                    if record.get("event") == "task_outcome":
                        results.append(record)
        except OSError:
            pass
        return results

    def compute_reward(self, record: dict[str, Any]) -> float:
        base = 1.0 if record.get("success") else -0.5
        efficiency_bonus = max(0, 0.3 - 0.1 * (record.get("docs_count", 0) - 1))
        return round(base + efficiency_bonus, 4)

    def recent_rewards(self, task_type: str | None = None, n: int = 50) -> list[float]:
        outcomes = self.query(task_type=task_type, limit=n)
        return [self.compute_reward(r) for r in outcomes]
