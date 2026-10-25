"""治理门禁负向测试：脚本必须真的会失败。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sanitize-for-push.sh"


def _run(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, SKILLOS_SANITIZE_ROOT=str(root))
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_clean_directory_passes(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_absolute_path_fails(tmp_path):
    leaked = "/Vol" + "umes/secret/data"
    (tmp_path / "app.py").write_text(f'ROOT = "{leaked}"\n', encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "绝对路径" in result.stdout


def test_api_key_fails(tmp_path):
    (tmp_path / "app.py").write_text('KEY = "sk-' + "a1b2c3d4e5f6g7h8i9j0" + '"\n', encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "密钥" in result.stdout


def test_private_key_fails(tmp_path):
    (tmp_path / "id.txt").write_text("-----BEGIN RSA " + "PRIVATE KEY-----\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 1


def test_proprietary_file_fails(tmp_path):
    (tmp_path / "SOUL.md").write_text("internal\n", encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 1
