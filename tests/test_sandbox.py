"""Tests for skillos.sandbox.process_sandbox — ProcessSandbox resource-limited execution"""

import os
import tempfile

import pytest

from skillos.sandbox.process_sandbox import HAS_RESOURCE, ProcessSandbox


class TestProcessSandbox:
    def test_basic_execution(self):
        sandbox = ProcessSandbox()
        script = 'import json,sys; print(json.dumps({"result":"hello"}))'
        result = sandbox.execute(script, {})
        assert result["status"] == "completed"
        assert result["output"] == {"result": "hello"}

    def test_timeout(self):
        sandbox = ProcessSandbox()
        script = "import time; time.sleep(999)"
        result = sandbox.execute(script, {}, timeout=1)
        assert result["status"] == "error"
        assert "timed out" in result["error"].lower()

    def test_invalid_script(self):
        sandbox = ProcessSandbox()
        script = "print("
        result = sandbox.execute(script, {})
        assert result["status"] == "error"

    @pytest.mark.skipif(not HAS_RESOURCE, reason="resource module not available")
    def test_resource_limits_cpu(self):
        sandbox = ProcessSandbox(resource_limits={"cpu_time_secs": 1})
        script = "x=0\nfor _ in range(10**8):\n x+=1\nprint(x)"
        result = sandbox.execute(script, {})
        assert result["status"] == "error"

    @pytest.mark.skipif(not HAS_RESOURCE, reason="resource module not available")
    def test_resource_limits_memory(self):
        sandbox = ProcessSandbox(resource_limits={"max_memory_mb": 5})
        script = "x=[0]*(10**8)\nprint('ok')"
        result = sandbox.execute(script, {})
        assert result["status"] == "error"

    def test_empty_script(self):
        sandbox = ProcessSandbox()
        result = sandbox.execute("", {})
        assert result["status"] == "error"

    def test_input_data(self):
        sandbox = ProcessSandbox()
        script = "import json,sys\nd=json.loads(sys.stdin.read())\nprint(json.dumps({'echo':d['key']}))"
        result = sandbox.execute(script, {"key": "value"})
        assert result["status"] == "completed"
        assert result["output"] == {"echo": "value"}

    def test_error_propagates(self):
        sandbox = ProcessSandbox()
        script = 'raise RuntimeError("boom")'
        result = sandbox.execute(script, {})
        assert result["status"] == "error"
        assert "RuntimeError" in result["error"]

    def test_temp_file_cleanup(self):
        sandbox = ProcessSandbox()
        tempdir = tempfile.gettempdir()
        before = {f for f in os.listdir(tempdir) if f.startswith("skillos_sandbox_")}
        sandbox.execute('import json; print(json.dumps({"ok":1}))', {})
        after = {f for f in os.listdir(tempdir) if f.startswith("skillos_sandbox_")}
        assert before == after

    def test_sandbox_reuse(self):
        sandbox = ProcessSandbox()
        r1 = sandbox.execute('import json; print(json.dumps({"n":1}))', {})
        assert r1["status"] == "completed"
        assert r1["output"] == {"n": 1}
        r2 = sandbox.execute('import json; print(json.dumps({"n":2}))', {})
        assert r2["status"] == "completed"
        assert r2["output"] == {"n": 2}

    def test_skill_id_propagation(self):
        sandbox = ProcessSandbox(skill_id="alice")
        script = 'import json; print(json.dumps({"ok":1}))'
        result = sandbox.execute(script, {})
        assert result["skill_id"] == "alice"

    def test_skill_id_override(self):
        sandbox = ProcessSandbox(skill_id="alice")
        script = 'import json; print(json.dumps({"ok":1}))'
        result = sandbox.execute(script, {}, skill_id="bob")
        assert result["skill_id"] == "bob"

    def test_non_json_output(self):
        sandbox = ProcessSandbox()
        script = "print('hello')"
        result = sandbox.execute(script, {})
        assert result["status"] == "error"
        assert "Expecting value" in result["error"]

    def test_exit_code_nonzero(self):
        sandbox = ProcessSandbox()
        script = "import sys; sys.exit(1)"
        result = sandbox.execute(script, {})
        assert result["status"] == "error"

    def test_timeout_kills_grandchildren(self):
        """C9：孙进程不逃逸超时——子进程 fork 后台进程后超时，整组被杀。"""
        sandbox = ProcessSandbox()
        script = (
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(999)'])\n"
            "import time; time.sleep(999)\n"
        )
        result = sandbox.execute(script, {}, timeout=1)
        assert result["status"] == "error"
        assert "timed out" in result["error"].lower()

    def test_output_size_limit(self):
        """C9：超大输出被拒绝，防止刷爆父进程内存。"""
        from skillos.sandbox.process_sandbox import MAX_OUTPUT_BYTES

        sandbox = ProcessSandbox()
        # 输出 2 倍上限的字符
        script = f"print('x' * ({MAX_OUTPUT_BYTES * 2}))"
        result = sandbox.execute(script, {})
        assert result["status"] == "error"
        assert "Output exceeds" in result["error"]
