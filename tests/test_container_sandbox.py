"""Tests for skillos.sandbox.container_sandbox — Docker 容器沙箱"""

from __future__ import annotations

import json

import pytest

from skillos.sandbox.container_sandbox import DockerSandbox

# 略：真实 Docker 可用性由环境决定，测试通过注入 docker_check / docker_run 保持确定性


class _FakeRunner:
    """注入的 docker 运行器，记录参数并返回可配置结果。"""

    def __init__(self, rc: int = 0, stdout: str = "{}", stderr: str = "") -> None:
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> object:
        self.calls.append(cmd)
        return type("R", (), {"returncode": self.rc, "stdout": self.stdout, "stderr": self.stderr})


class TestDockerSandboxCommandAssembly:
    def test_builds_docker_run_command(self) -> None:
        sandbox = DockerSandbox(
            image="python:3.11-slim",
            resource_limits={"max_memory_mb": 256, "cpu_quota_pct": 0.5},
            network_mode="none",
            docker_available=lambda: True,
        )
        cmd = sandbox._build_command("script.py", timeout=10)
        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        joined = " ".join(cmd)
        # 核心安全参数
        assert "--rm" in joined
        assert "--interactive" in joined
        assert "--network" in joined and "none" in joined
        assert "--memory" in joined and "256m" in joined
        assert "--cpus" in joined and "0.5" in joined
        assert "python:3.11-slim" in joined
        assert "script.py" in cmd[-1] or "script.py" in joined

    def test_readonly_and_no_new_privileges(self) -> None:
        sandbox = DockerSandbox(
            image="python:3.11-slim",
            docker_available=lambda: True,
        )
        cmd = sandbox._build_command("s.py", timeout=5)
        joined = " ".join(cmd)
        assert "--read-only" in joined
        assert "--cap-drop" in joined and "ALL" in joined
        assert "--security-opt" in joined and "no-new-privileges" in joined

    def test_docker_unavailable_rejected(self) -> None:
        sandbox = DockerSandbox(
            image="python:3.11-slim",
            docker_available=lambda: False,
        )
        result = sandbox.execute("print(1)", timeout=5)
        assert result["status"] == "rejected"
        assert "docker" in result["error"].lower()

    def test_timeout_injects_alarm(self) -> None:
        sandbox = DockerSandbox(
            image="python:3.11-slim",
            docker_available=lambda: True,
        )
        wrapped = sandbox._wrap_timeout("print(1)", timeout=7)
        assert "signal.alarm(7)" in wrapped
        assert "TimeoutError" in wrapped


class TestDockerSandboxExecution:
    def test_success_path_decodes_json(self) -> None:
        runner = _FakeRunner(
            stdout=json.dumps({"skill_id": "s1", "status": "completed", "output": {"ok": 1}})
        )
        sandbox = DockerSandbox(docker_available=lambda: True, runner=runner)
        result = sandbox.execute("import sys; sys.stdout.write('{}')", timeout=5)
        assert result["status"] == "completed"
        assert result["output"] == {"skill_id": "s1", "status": "completed", "output": {"ok": 1}}
        assert runner.calls  # docker run 被调用

    def test_nonzero_exit_reports_error(self) -> None:
        runner = _FakeRunner(rc=1, stderr="Traceback: boom")
        sandbox = DockerSandbox(docker_available=lambda: True, runner=runner)
        result = sandbox.execute("raise RuntimeError('boom')", timeout=5)
        assert result["status"] == "error"
        assert "boom" in result["error"]

    def test_invalid_json_reports_error(self) -> None:
        runner = _FakeRunner(stdout="not json")
        sandbox = DockerSandbox(docker_available=lambda: True, runner=runner)
        result = sandbox.execute("print('not json')", timeout=5)
        assert result["status"] == "error"


class TestDockerSandboxKernelIntegration:
    def test_kernel_docker_env_executes(self) -> None:
        """SkillKernel 的 docker execution_env 不应再是 stub 拒绝"""
        import asyncio

        from skillos.kernel.skill_kernel import SkillKernel, ToolChain

        kernel = SkillKernel()
        chain = ToolChain(
            skill_id="sk-docker",
            tools=[],
            mcp_connectors=[],
            a2a_adapters=[],
            execution_env="docker",
        )
        result = asyncio.run(kernel.execute(chain, {"echo": "hi"}))
        if result["status"] == "rejected" and "docker" in result.get("error", "").lower():
            pytest.skip("docker 不可用，跳过集成")
        assert result["status"] in ("completed", "error")
