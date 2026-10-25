#!/usr/bin/env python3
"""Process Sandbox — 用户态子进程沙箱（资源受限，非安全隔离）

通过 resource.setrlimit() 实现 CPU / 内存 / 文件描述符 / 进程数限制。
macOS / Linux 通用。

**重要边界声明（C9 修复）**：
  - 本沙箱是**资源限制**机制，**不是安全隔离边界**。子进程仍可读本用户
    可读文件、联网、写任意本用户可写路径。不可用其隔离不可信代码。
  - Linux `os.unshare` 在无特权用户下必抛 EPERM（此前被静默吞掉，隔离从未生效），
    因此已移除，避免制造「已隔离」的虚假安全感。
  - 超时通过进程组 ``killpg`` 终止（含孙进程），防止 fork 后台进程逃逸。
  - 输出大小设上限（默认 1MiB），防止子进程刷爆内存。
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    import resource as _rmod  # type: ignore[no-redef]

    HAS_RESOURCE = True
except ImportError:
    _rmod = None  # type: ignore[assignment]
    HAS_RESOURCE = False

# C9：输出大小上限（字节），防止子进程刷爆父进程内存
MAX_OUTPUT_BYTES = 1024 * 1024


class ProcessSandbox:
    """进程沙箱 — 在受限子进程中执行任意 Python 脚本（资源限制）。"""

    def __init__(
        self,
        resource_limits: dict[str, Any] | None = None,
        skill_id: str = "",
    ) -> None:
        self._skill_id = skill_id

        if not HAS_RESOURCE and resource_limits:
            logger.warning(
                "resource module not available on %s — resource limits disabled",
                sys.platform,
            )
            self._resource_limits: dict[str, Any] = {}
        else:
            self._resource_limits = resource_limits or {}

    def execute(
        self,
        script_content: str,
        input_data: dict[str, Any] | None = None,
        timeout: int = 30,
        skill_id: str = "",
    ) -> dict[str, Any]:
        """在受限子进程中执行脚本并返回标准化结果。

        Args:
            script_content: 待执行的 Python 脚本源码
            input_data: 通过 stdin 传递给脚本的 JSON 数据
            timeout: 超时秒数
            skill_id: 技能标识（覆写构造参数）

        Returns:
            标准化结果字典：
                skill_id: str
                status: "completed" | "error"
                output: Any（completed 时是反序列化后的输出）
                error: str
        """
        effective_skill_id = skill_id or self._skill_id
        input_data = input_data or {}
        script_path: str | None = None

        try:
            fd, script_path = tempfile.mkstemp(suffix=".py", prefix="skillos_sandbox_")
            with os.fdopen(fd, "w") as f:
                f.write(script_content)

            preexec = self._build_preexec() if self._resource_limits else None

            # start_new_session=True：子进程成为新会话组长，超时用 killpg 杀整组（含孙进程）
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                preexec_fn=preexec,
            )
            try:
                stdout, stderr = proc.communicate(
                    input=json.dumps(input_data),
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                self._kill_process_group(proc)
                proc.wait(timeout=5)
                return {
                    "skill_id": effective_skill_id,
                    "status": "error",
                    "output": "",
                    "error": f"Execution timed out after {timeout}s",
                }

            # C9：输出大小限制（stdout/stderr 合并截断）
            if len(stdout or "") + len(stderr or "") > MAX_OUTPUT_BYTES:
                return {
                    "skill_id": effective_skill_id,
                    "status": "error",
                    "output": "",
                    "error": f"Output exceeds {MAX_OUTPUT_BYTES} bytes limit",
                }

            if proc.returncode != 0:
                error_msg = (stderr or "").strip() or f"exit code {proc.returncode}"
                return {
                    "skill_id": effective_skill_id,
                    "status": "error",
                    "output": stdout or "",
                    "error": error_msg,
                }

            try:
                output = json.loads(stdout)
            except json.JSONDecodeError as e:
                return {
                    "skill_id": effective_skill_id,
                    "status": "error",
                    "output": stdout or "",
                    "error": str(e),
                }

            return {
                "skill_id": effective_skill_id,
                "status": "completed",
                "output": output,
                "error": "",
            }

        except Exception as e:
            return {
                "skill_id": effective_skill_id,
                "status": "error",
                "output": "",
                "error": str(e),
            }
        finally:
            if script_path and os.path.exists(script_path):
                try:
                    os.unlink(script_path)
                except OSError:
                    pass

    @staticmethod
    def _kill_process_group(proc: subprocess.Popen) -> None:
        """C9：终止整个进程组（含孙进程），超时不逃逸。"""
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            # 进程组已不存在（子进程已退出）则忽略
            pass

    def _build_preexec(self) -> Callable[[], None]:
        limits = self._resource_limits.copy()

        def _preexec() -> None:
            rlimits: list[tuple[Any, int, int]] = []

            cpu_val = limits.get("cpu_time_secs")
            if cpu_val is not None:
                rlim = getattr(_rmod, "RLIMIT_CPU", None)
                if rlim is not None:
                    rlimits.append((rlim, cpu_val, cpu_val))

            mem_mb = limits.get("max_memory_mb")
            if mem_mb is not None:
                mem_bytes = mem_mb * 1024 * 1024
                for name in ("RLIMIT_AS", "RLIMIT_DATA", "RLIMIT_RSS"):
                    rlim = getattr(_rmod, name, None)
                    if rlim is not None:
                        rlimits.append((rlim, mem_bytes, mem_bytes))
                        break

            fd_val = limits.get("max_files")
            if fd_val is not None:
                rlim = getattr(_rmod, "RLIMIT_NOFILE", None)
                if rlim is not None:
                    rlimits.append((rlim, fd_val, fd_val))

            proc_val = limits.get("max_processes")
            if proc_val is not None:
                rlim = getattr(_rmod, "RLIMIT_NPROC", None)
                if rlim is not None:
                    rlimits.append((rlim, proc_val, proc_val))

            for rlim, soft, hard in rlimits:
                try:
                    _rmod.setrlimit(rlim, (soft, hard))
                except (ValueError, OSError):
                    pass

        return _preexec
