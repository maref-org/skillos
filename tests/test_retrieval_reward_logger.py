"""Tests for skillos.retrieval.reward_logger"""

import tempfile
from pathlib import Path

import pytest

from skillos.retrieval.reward_logger import RewardLogger


class TestRewardLogger:
    @pytest.fixture
    def logger(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield RewardLogger(log_path=Path(tmp) / "rewards.jsonl")

    def test_log_task_start(self, logger):
        logger.log_task_start("t1", "audit", tags=["meta"], agent_id="agent-a")
        assert "t1" in logger._active_tasks
        assert logger._active_tasks["t1"]["task_type"] == "audit"

    def test_log_doc_read(self, logger):
        logger.log_task_start("t1", "audit")
        logger.log_doc_read("t1", "docs/report.md")
        assert "docs/report.md" in logger._active_tasks["t1"]["docs_read"]

    def test_log_task_outcome_success(self, logger):
        logger.log_task_start("t1", "audit", tags=["meta"])
        logger.log_doc_read("t1", "docs/report.md")
        logger.log_task_outcome("t1", success=True)
        assert "t1" not in logger._active_tasks

    def test_compute_reward_success(self, logger):
        logger.log_task_start("t1", "audit", tags=["meta"])
        logger.log_doc_read("t1", "docs/a.md")
        logger.log_task_outcome("t1", success=True)
        reward = logger.compute_reward({"success": True, "docs_count": 1})
        assert reward == 1.3  # 1.0 base + 0.3 efficiency

    def test_compute_reward_failure(self, logger):
        reward = logger.compute_reward({"success": False, "docs_count": 3})
        # -0.5 base + max(0, 0.3 - 0.2) efficiency = -0.4
        assert reward == -0.4

    def test_query_by_type(self, logger):
        logger.log_task_start("t1", "audit", tags=["meta"])
        logger.log_task_outcome("t1", success=True)
        logger.log_task_start("t2", "deploy", tags=["ops"])
        logger.log_task_outcome("t2", success=False)
        results = logger.query(task_type="audit")
        assert len(results) == 1
        assert results[0]["task_type"] == "audit"

    def test_recent_rewards(self, logger):
        logger.log_task_start("t1", "audit")
        logger.log_doc_read("t1", "docs/a.md")
        logger.log_task_outcome("t1", success=True)
        rewards = logger.recent_rewards()
        assert len(rewards) == 1
        assert rewards[0] > 0

    def test_log_persistence(self, logger):
        logger.log_task_start("t1", "audit", tags=["meta"])
        logger.log_doc_read("t1", "docs/report.md")
        logger.log_task_outcome("t1", success=True)
        assert logger._path.exists()
        lines = logger._path.read_text().strip().split("\n")
        # 3 events: task_start, doc_read, task_outcome
        assert len(lines) == 3
