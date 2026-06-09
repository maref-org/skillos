#!/usr/bin/env python3
"""MAS Capabilities Integration Tests

Tests for Layer 5 MAS dimension capabilities:
  - Session Isolation
  - State Persistence
  - Task Scheduling
  - Remote Bridge Control
"""

import tempfile
from pathlib import Path

import pytest

from skillos.kernel.session_isolator import ExecutionResult, SessionIsolator
from skillos.kernel.state_persistor import PersistentState, StatePersistor
from skillos.kernel.task_scheduler import TaskScheduler
from skillos.protocol.remote_control import RemoteBridge, RemoteCommand


class TestSessionIsolator:
    @pytest.fixture
    def isolator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SessionIsolator(base_dir=tmpdir)

    @pytest.mark.asyncio
    async def test_create_isolated_session(self, isolator):
        ctx = await isolator.create_isolated_session(
            session_id="test-001",
            resource_limits={"timeout_seconds": 60},
        )
        assert ctx.session_id == "test-001"
        assert ctx.sandbox_id == "sandbox_test-001"
        assert Path(ctx.worktree_path).exists()
        assert "test-001" in isolator.active_sessions

    @pytest.mark.asyncio
    async def test_create_session_auto_id(self, isolator):
        ctx = await isolator.create_isolated_session()
        assert ctx.session_id is not None
        assert ctx.sandbox_id.startswith("sandbox_")

    @pytest.mark.asyncio
    async def test_execute_in_isolation(self, isolator):
        await isolator.create_isolated_session(session_id="test-002")
        result = await isolator.execute_in_isolation("test-002", "echo hello")
        assert isinstance(result, ExecutionResult)
        assert "hello" in result.stdout
        assert result.exit_code == 0
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_timeout(self, isolator):
        await isolator.create_isolated_session(
            session_id="test-003",
            resource_limits={"timeout_seconds": 1},
        )
        result = await isolator.execute_in_isolation("test-003", "sleep 10", timeout=1)
        assert result.timed_out is True
        assert result.exit_code == -1

    @pytest.mark.asyncio
    async def test_execute_invalid_session(self, isolator):
        with pytest.raises(ValueError, match="not found"):
            await isolator.execute_in_isolation("nonexistent", "echo test")

    @pytest.mark.asyncio
    async def test_cleanup_session(self, isolator):
        await isolator.create_isolated_session(session_id="test-004")
        result = await isolator.cleanup_session("test-004")
        assert result is True
        assert "test-004" not in isolator.active_sessions

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent(self, isolator):
        result = await isolator.cleanup_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_all(self, isolator):
        await isolator.create_isolated_session(session_id="test-005")
        await isolator.create_isolated_session(session_id="test-006")
        count = await isolator.cleanup_all()
        assert count == 2
        assert len(isolator.active_sessions) == 0

    @pytest.mark.asyncio
    async def test_list_active_sessions(self, isolator):
        await isolator.create_isolated_session(session_id="test-007")
        sessions = isolator.list_active_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "test-007"


class TestStatePersistor:
    @pytest.fixture
    def persistor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_state.db"
            yield StatePersistor(db_path=str(db_path))

    def test_save_and_load_state(self, persistor):
        state = PersistentState(
            session_id="sess-001",
            state_key="context",
            state_value={"query": "test", "results": 5},
        )
        assert persistor.save_state(state) is True

        loaded = persistor.load_state("sess-001", "context")
        assert loaded == {"query": "test", "results": 5}

    def test_load_nonexistent_state(self, persistor):
        result = persistor.load_state("nonexistent", "key")
        assert result is None

    def test_delete_state(self, persistor):
        state = PersistentState(
            session_id="sess-002",
            state_key="temp",
            state_value="value",
        )
        persistor.save_state(state)
        assert persistor.delete_state("sess-002", "temp") is True
        assert persistor.load_state("sess-002", "temp") is None

    def test_ttl_expiry(self, persistor):
        state = PersistentState(
            session_id="sess-003",
            state_key="expiring",
            state_value="data",
            ttl_seconds=1,
        )
        persistor.save_state(state)
        assert persistor.load_state("sess-003", "expiring") == "data"

        import time

        time.sleep(1.1)
        assert persistor.load_state("sess-003", "expiring") is None

    def test_list_states(self, persistor):
        persistor.save_state(PersistentState("sess-004", "key1", "val1"))
        persistor.save_state(PersistentState("sess-004", "key2", "val2"))
        states = persistor.list_states("sess-004")
        assert len(states) == 2
        keys = {s["key"] for s in states}
        assert keys == {"key1", "key2"}

    def test_save_task_result(self, persistor):
        assert (
            persistor.save_task_result(
                task_id="task-001",
                session_id="sess-005",
                result={"output": "done"},
                context={"input": "test"},
            )
            is True
        )

        history = persistor.get_task_history("sess-005")
        assert len(history) == 1
        assert history[0]["task_id"] == "task-001"
        assert history[0]["result"] == {"output": "done"}

    def test_get_task_by_id(self, persistor):
        persistor.save_task_result(
            task_id="task-002",
            session_id="sess-006",
            result={"data": 123},
            context={},
        )
        task = persistor.get_task_by_id("task-002")
        assert task is not None
        assert task["task_id"] == "task-002"

    def test_get_nonexistent_task(self, persistor):
        assert persistor.get_task_by_id("nonexistent") is None

    def test_cleanup_expired(self, persistor):
        persistor.save_state(PersistentState("sess-007", "expire1", "val", ttl_seconds=1))
        persistor.save_state(PersistentState("sess-007", "permanent", "val", ttl_seconds=0))

        import time

        time.sleep(1.1)
        count = persistor.cleanup_expired()
        assert count == 1

    def test_get_stats(self, persistor):
        persistor.save_state(PersistentState("sess-008", "k1", "v1"))
        persistor.save_state(PersistentState("sess-009", "k2", "v2"))
        persistor.save_task_result("task-003", "sess-008", {}, {})

        stats = persistor.get_stats()
        assert stats["total_states"] == 2
        assert stats["total_tasks"] == 1
        assert stats["total_sessions"] == 2


class TestTaskScheduler:
    @pytest.fixture
    def scheduler(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "tasks.json"
            yield TaskScheduler(config_path=str(config_path))

    def test_add_task(self, scheduler):
        task = scheduler.add_task(
            task_id="cron-001",
            name="Daily Report",
            cron_expression="0 9 * * *",
            handler="daily_report",
        )
        assert task.task_id == "cron-001"
        assert task.enabled is True
        assert task.next_run is not None

    def test_add_invalid_cron(self, scheduler):
        with pytest.raises(ValueError, match="Invalid cron"):
            scheduler.add_task("bad", "Bad", "invalid", "handler")

    def test_remove_task(self, scheduler):
        scheduler.add_task("cron-002", "Test", "0 10 * * *", "handler")
        assert scheduler.remove_task("cron-002") is True
        assert scheduler.get_task("cron-002") is None

    def test_remove_nonexistent(self, scheduler):
        assert scheduler.remove_task("nonexistent") is False

    def test_enable_disable_task(self, scheduler):
        scheduler.add_task("cron-003", "Test", "0 11 * * *", "handler")
        assert scheduler.disable_task("cron-003") is True
        assert scheduler.get_task("cron-003").enabled is False
        assert scheduler.enable_task("cron-003") is True
        assert scheduler.get_task("cron-003").enabled is True

    def test_list_tasks(self, scheduler):
        scheduler.add_task("cron-004", "A", "0 12 * * *", "handler_a")
        scheduler.add_task("cron-005", "B", "0 13 * * *", "handler_b")
        tasks = scheduler.list_tasks()
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        await scheduler.start()
        assert scheduler._running is True
        await scheduler.stop()
        assert scheduler._running is False


class TestRemoteBridge:
    @pytest.fixture
    def bridge(self):
        return RemoteBridge()

    @pytest.mark.asyncio
    async def test_connect_bridge(self, bridge):
        result = await bridge.connect_bridge("sess-001", "http://remote:8000", "key123")
        assert result["status"] == "connected"
        assert result["session_id"] == "sess-001"

    @pytest.mark.asyncio
    async def test_disconnect_bridge(self, bridge):
        await bridge.connect_bridge("sess-002", "http://remote:8000", "key")
        result = await bridge.disconnect_bridge("sess-002")
        assert result["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self, bridge):
        with pytest.raises(ValueError, match="not found"):
            await bridge.disconnect_bridge("nonexistent")

    @pytest.mark.asyncio
    async def test_get_bridge_status(self, bridge):
        await bridge.connect_bridge("sess-003", "http://remote:8000", "key")
        status = await bridge.get_bridge_status("sess-003")
        assert status["status"] == "connected"
        assert status["remote_url"] == "http://remote:8000"

    @pytest.mark.asyncio
    async def test_list_bridges(self, bridge):
        await bridge.connect_bridge("sess-004", "http://remote1:8000", "key1")
        await bridge.connect_bridge("sess-005", "http://remote2:8000", "key2")
        bridges = await bridge.list_bridges()
        assert len(bridges) == 2

    @pytest.mark.asyncio
    async def test_execute_remote_command_skill_execute(self, bridge):
        cmd = RemoteCommand(
            command="skill_execute",
            session_id="sess-006",
            params={"skill_name": "brainstorming"},
        )
        result = await bridge.execute_remote_command(cmd)
        assert result.status == "success"
        assert result.result["skill_name"] == "brainstorming"

    @pytest.mark.asyncio
    async def test_execute_unknown_command(self, bridge):
        cmd = RemoteCommand(command="unknown_cmd")
        result = await bridge.execute_remote_command(cmd)
        assert result.status == "error"
        assert "Unknown command" in result.error

    @pytest.mark.asyncio
    async def test_update_heartbeat(self, bridge):
        await bridge.connect_bridge("sess-007", "http://remote:8000", "key")
        assert await bridge.update_heartbeat("sess-007") is True
        assert await bridge.update_heartbeat("nonexistent") is False

    @pytest.mark.asyncio
    async def test_get_stats(self, bridge):
        await bridge.connect_bridge("sess-008", "http://remote:8000", "key")
        stats = bridge.get_stats()
        assert stats["total_bridges"] == 1
        assert stats["connected_bridges"] == 1
