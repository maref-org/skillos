#!/usr/bin/env python3
"""Docker Sandbox — 容器级沙箱执行环境（安全隔离）

P1 例外 #1 修复：以真实容器隔离取代仅资源限制的进程模拟。

安全特性（对齐 do-no-go 修复计划）:
  - 无网络: --network=none
  - 只读根: --read-only
  - 无特权: --cap-drop=ALL + --security-opt=no-new-privileges
  - 非 root: --user=65534:65534 (nobody)
  - 内存 / CPU / 进程数限制
  - 超时终止: 容器内 GNU timeout 包装（避免父进程 killpg 无法穿透容器）

**边界声明**: 容器隔离比进程级强得多，但非内核级 sandbox（无 seccomp 模式
filters / namespaces 之外的自定义策略）。不可信代码仍需在受控 CI 主机运行。
macOS 下 docker-socket 挂载为 VM socket；生产 Linux 建议 rootless。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess  # nosec B404 - 执行受控 docker 命令（白名单列表），不使用 shell
import tempfile
from typing import Any, Callable, TypeAlias

logger = logging.getLogger(__name__)

RunnerResult: TypeAlias = Any


def _default_docker_available() -> bool:
    try:
        return (
            subprocess.run(  # nosec B603 B607 - 仅探测 docker 可用性
                ["docker", "info"],  # noqa: S607
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def _default_runner(cmd: list[str], **kwargs: Any) -> RunnerResult:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)  # nosec B603


class DockerSandbox:
    """容器沙箱 — 在无网络、只读、非 root 容器中执行 Python 脚本。"""

    def __init__(
        self,
        image: str = "python:3.11-slim",
        resource_limits: dict[str, Any] | None = None,
        network_mode: str = "none",
        docker_available: Callable[[], bool] | None = None,
        runner: Callable[..., RunnerResult] | None = None,
        timeout: int = 30,
    ) -> None:
        self._image = image
        self._limits = resource_limits or {}
        self._network_mode = network_mode
        self._docker_available = docker_available or _default_docker_available
        self._runner = runner or _default_runner
        self._default_timeout = timeout

    def _build_command(self, script_path: str, timeout: int) -> list[str]:
        """构造 docker run 命令（含安全约束）。

        超时由脚本内 signal.alarm 自终止（见 _wrap_timeout）+ 外层
        subprocess timeout 兜底双层实现；不使用容器内 GNU timeout
        包装器（其会把 stdin 重定向到 /dev/null，导致脚本读不到输入）。
        """
        cmd = [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--network",
            self._network_mode,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--tmpfs",
            "/tmp:rw,size=64m",  # nosec B108 - 容器内挂载点（仅容器内可见），非宿主路径
        ]
        limits = self._limits
        mem_mb = limits.get("max_memory_mb")
        if mem_mb:
            cmd += ["--memory", f"{mem_mb}m"]
        cpu = limits.get("cpu_quota_pct")
        if cpu:
            cmd += ["--cpus", str(cpu)]
        pids = limits.get("max_processes")
        if pids:
            cmd += ["--pids-limit", str(pids)]

        cmd += [
            "--volume",
            f"{script_path}:/sandbox/script.py:ro",
            self._image,
            "python3",
            "/sandbox/script.py",
        ]
        return cmd

    @staticmethod
    def _wrap_timeout(script_content: str, timeout: int) -> str:
        """在脚本头部注入 signal.alarm 超时自终止保护。"""
        preamble = (
            "import signal\n"
            "def _skillos_timeout(sig, frame):\n"
            "    raise TimeoutError('sandbox execution timed out')\n"
            "signal.signal(signal.SIGALRM, _skillos_timeout)\n"
            f"signal.alarm({max(1, timeout)})\n"
        )
        return preamble + script_content

    def execute(
        self,
        script_content: str,
        input_data: dict[str, Any] | None = None,
        timeout: int = 0,
        skill_id: str = "",
    ) -> dict[str, Any]:
        """在容器沙箱中执行脚本并返回标准化结果。

        与 ProcessSandbox.execute 返回结构一致：
            skill_id / status ("completed"|"error"|"rejected") / output / error
        """
        timeout = timeout or self._default_timeout
        input_data = input_data or {}
        script_path: str | None = None

        if not self._docker_available():
            return {
                "skill_id": skill_id,
                "status": "rejected",
                "output": None,
                "error": "docker daemon not available",
            }

        try:
            fd, script_path = tempfile.mkstemp(suffix=".py", prefix="skillos_docker_")
            with os.fdopen(fd, "w") as f:
                f.write(self._wrap_timeout(script_content, timeout))

            proc = self._runner(
                self._build_command(script_path, timeout),
                input=json.dumps(input_data),
                timeout=timeout + 30,
            )
        except Exception as exc:
            logger.warning("Docker sandbox execution error: %s", exc)
            return {
                "skill_id": skill_id,
                "status": "error",
                "output": None,
                "error": str(exc),
            }
        finally:
            if script_path and os.path.exists(script_path):
                try:
                    os.unlink(script_path)
                except OSError:
                    pass

        if proc.returncode != 0:
            return {
                "skill_id": skill_id,
                "status": "error",
                "output": proc.stdout or "",
                "error": (proc.stderr or "").strip() or f"exit code {proc.returncode}",
            }

        try:
            output = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            return {
                "skill_id": skill_id,
                "status": "error",
                "output": proc.stdout or "",
                "error": f"invalid JSON output: {e}",
            }

        return {
            "skill_id": skill_id,
            "status": "completed",
            "output": output,
            "error": "",
        }
