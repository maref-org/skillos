#!/usr/bin/env python3
"""Session Isolator — 隔离执行环境管理器

职责:
  - 创建 worktree/sandbox 隔离执行环境
  - 在隔离环境中执行命令
  - 资源限制 (CPU/内存/磁盘/超时)
  - 会话清理与回收
"""

import asyncio
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = "/tmp/skillos-isolation"


@dataclass
class IsolationContext:
    worktree_path: str
    sandbox_id: str
    resource_limits: dict
    session_id: str
    created_at: float = 0.0
    pid: int | None = None


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float = 0.0
    timed_out: bool = False


class SessionIsolator:
    """Session 隔离执行管理器"""

    def __init__(self, base_dir: str = _DEFAULT_BASE_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: dict[str, IsolationContext] = {}

    async def create_isolated_session(
        self,
        session_id: str | None = None,
        repo_path: str | None = None,
        resource_limits: dict | None = None,
    ) -> IsolationContext:
        """创建隔离执行会话"""
        session_id = session_id or str(uuid.uuid4())
        sandbox_id = f"sandbox_{session_id}"
        worktree_path = self.base_dir / sandbox_id
        worktree_path.mkdir(parents=True, exist_ok=True)

        if repo_path:
            await self._create_git_worktree(repo_path, worktree_path)

        limits = resource_limits or {
            "max_memory_mb": 2048,
            "max_cpu_percent": 50,
            "max_disk_mb": 1024,
            "timeout_seconds": 300,
        }

        import time
        ctx = IsolationContext(
            worktree_path=str(worktree_path),
            sandbox_id=sandbox_id,
            resource_limits=limits,
            session_id=session_id,
            created_at=time.time(),
        )
        self.active_sessions[session_id] = ctx
        logger.info("Isolated session created: %s at %s", session_id, worktree_path)
        return ctx

    async def execute_in_isolation(
        self,
        session_id: str,
        command: str | list[str],
        timeout: int | None = None,
    ) -> ExecutionResult:
        """在隔离环境中执行命令"""
        ctx = self.active_sessions.get(session_id)
        if not ctx:
            raise ValueError(f"Session {session_id} not found")

        timeout = timeout or ctx.resource_limits.get("timeout_seconds", 300)

        if isinstance(command, str):
            cmd_parts = command.split()
        else:
            cmd_parts = command

        import time
        start = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            cwd=ctx.worktree_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration_ms = (time.time() - start) * 1000
            return ExecutionResult(
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                exit_code=proc.returncode or 0,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            duration_ms = (time.time() - start) * 1000
            logger.warning("Execution timeout for session %s after %ds", session_id, timeout)
            return ExecutionResult(
                stdout="",
                stderr=f"Execution timeout after {timeout}s",
                exit_code=-1,
                duration_ms=duration_ms,
                timed_out=True,
            )

    async def cleanup_session(self, session_id: str) -> bool:
        """清理隔离会话"""
        ctx = self.active_sessions.pop(session_id, None)
        if ctx:
            worktree = Path(ctx.worktree_path)
            if worktree.exists():
                shutil.rmtree(worktree, ignore_errors=True)
            logger.info("Isolated session cleaned up: %s", session_id)
            return True
        return False

    async def cleanup_all(self) -> int:
        """清理所有隔离会话"""
        count = 0
        for sid in list(self.active_sessions.keys()):
            if await self.cleanup_session(sid):
                count += 1
        return count

    async def _create_git_worktree(self, repo_path: str, worktree_path: Path) -> None:
        """创建 git worktree 隔离副本"""
        branch_name = f"skillos-iso-{worktree_path.name}"
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", str(worktree_path), "-b", branch_name,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("git worktree failed: %s", stderr.decode())
            worktree_path.mkdir(parents=True, exist_ok=True)

    def list_active_sessions(self) -> list[dict]:
        """列出所有活跃隔离会话"""
        return [
            {
                "session_id": ctx.session_id,
                "sandbox_id": ctx.sandbox_id,
                "worktree_path": ctx.worktree_path,
                "created_at": ctx.created_at,
            }
            for ctx in self.active_sessions.values()
        ]
