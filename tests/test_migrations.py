"""Tests for C11 — alembic 迁移链可执行 + 幂等循环"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytest.importorskip("alembic")


def _run_alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    """在隔离 SQLite 上运行 alembic 命令。"""
    env = {"SKILLOS_DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(REPO_ROOT),
        env={**__import__("os").environ, **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def _output(r: subprocess.CompletedProcess) -> str:
    """alembic 日志经 logging 输出到 stderr，合并判断。"""
    return (r.stdout or "") + (r.stderr or "")


class TestMigrationChain:
    def test_upgrade_head_succeeds(self, tmp_path):
        """C11：空库上 001→014 全部迁移可执行。"""
        db = f"sqlite:///{tmp_path}/mig.db"
        r = _run_alembic(db, "upgrade", "head")
        assert r.returncode == 0, r.stderr[-2000:]
        assert "Running upgrade" in _output(r)

    def test_upgrade_idempotent(self, tmp_path):
        """C11：重跑 upgrade head 无操作（迁移链幂等，008/009 不重复 ALTER）。"""
        db = f"sqlite:///{tmp_path}/mig.db"
        assert _run_alembic(db, "upgrade", "head").returncode == 0
        r2 = _run_alembic(db, "upgrade", "head")
        assert r2.returncode == 0, r2.stderr[-2000:]
        assert "Running upgrade" not in _output(r2)

    def test_upgrade_downgrade_upgrade_cycle(self, tmp_path):
        """C11：upgrade→downgrade base→upgrade 循环无错。"""
        db = f"sqlite:///{tmp_path}/mig.db"
        assert _run_alembic(db, "upgrade", "head").returncode == 0
        down = _run_alembic(db, "downgrade", "base")
        assert down.returncode == 0, down.stderr[-2000:]
        up2 = _run_alembic(db, "upgrade", "head")
        assert up2.returncode == 0, up2.stderr[-2000:]
        assert "Running upgrade" in _output(up2)
