#!/usr/bin/env python3
"""skillos.cswdp.quality_gate — 质量门禁自动化

执行静态扫描+测试组合，输出 QualityReport。
默认检查项（roadmap §5.2.4）:
  ruff / mypy / pytest / bandit / pip-audit
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - 执行受控的质量门禁命令（白名单列表），不使用 shell
import time
from typing import Any

from skillos.cswdp.models import QualityCheckResult, QualityReport


class QualityGate:
    CHECKS: dict[str, list[str]] = {
        "ruff": ["ruff", "check", "."],
        "mypy": ["mypy", "--strict", "skillos/"],
        "pytest": [
            "pytest",
            "--cov=skillos",
            "--cov-report=term-missing",
            "-q",
        ],
        "bandit": ["bandit", "-r", "skillos/", "-q"],
        "pip_audit": ["pip-audit"],
    }

    THRESHOLDS = {
        "pytest_coverage": 0.80,
    }

    def __init__(self, checks: dict[str, list[str]] | None = None) -> None:
        if checks is not None:
            self.CHECKS = checks
        self._timeout = 300

    def _run_check(self, name: str, command: list[str]) -> QualityCheckResult:
        import os

        deadline = time.monotonic() + self._timeout
        started = time.monotonic()
        tail: str = ""
        passed = False

        if not shutil.which(command[0]):
            tail = f"binary not found: {command[0]}"
            return QualityCheckResult(
                name=name, command=" ".join(command), passed=False,
                duration_sec=round(time.monotonic() - started, 3), output_tail=tail,
            )

        try:
            proc = subprocess.Popen(  # nosec B603 - 无 shell，命令来自配置白名单
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                cwd=os.getcwd(),
            )
            lines: list[str] = []
            if proc.stdout is None:  # 防御：PIPE 模式下不可能为 None
                tail = "error: stdout not captured"
                return QualityCheckResult(
                    name=name, command=" ".join(command), passed=False,
                    duration_sec=round(time.monotonic() - started, 3),
                    output_tail=tail,
                )
            for line in proc.stdout:
                if time.monotonic() > deadline:
                    proc.kill()
                    tail = "TIMEOUT exceeded"
                    break
                lines.append(line.rstrip())
            rc = proc.wait(timeout=30)
            passed = rc == 0
            out = "\n".join(lines[-20:]) if lines else ""
            tail = out[-500:]
            if name == "pytest" and passed:
                cov_line = next((ln for ln in reversed(lines) if "TOTAL" in ln and "%" in ln), "")
                digits = "".join(ch for ch in cov_line.split() if ch.endswith("%"))
                if digits:
                    tail = tail + f"\nCOVERAGE {digits}"
        except (subprocess.SubprocessError, OSError) as exc:
            tail = f"error: {exc}"

        return QualityCheckResult(
            name=name, command=" ".join(command), passed=passed,
            duration_sec=round(time.monotonic() - started, 3), output_tail=tail,
        )

    def run_all(self) -> QualityReport:
        results: dict[str, QualityCheckResult] = {}
        for name, command in self.CHECKS.items():
            results[name] = self._run_check(name, command)
        passed = all(r.passed for r in results.values())
        return QualityReport(results=results, passed=passed)

    def run_named(self, *names: str) -> QualityReport:
        results = {
            name: self._run_check(name, command)
            for name, command in self.CHECKS.items()
            if name in names
        }
        return QualityReport(
            results=results, passed=all(r.passed for r in results.values())
        )

    def parse_coverage(self, report: QualityReport) -> float:
        """从 pytest 输出尾部解析总覆盖率（0.0~1.0），默认 0.0"""
        result = report.results.get("pytest")
        if result is None or not result.output_tail:
            return 0.0
        for token in result.output_tail.split():
            tok = token.strip()
            if tok.endswith("%") and tok[:-1].replace(".", "", 1).isdigit():
                return min(float(tok[:-1]) / 100.0, 1.0)
        return 0.0

    def evaluate(self, report: QualityReport) -> dict[str, Any]:
        coverage = self.parse_coverage(report)
        report.coverage = coverage
        threshold = self.THRESHOLDS["pytest_coverage"]
        all_passed = bool(report.results) and all(r.passed for r in report.results.values())
        if "pytest" in report.results and report.results["pytest"].passed:
            all_passed = all_passed and coverage >= threshold
        report.passed = all_passed
        return {
            "passed": report.passed,
            "coverage": coverage,
            "coverage_threshold": threshold,
            "checks": {k: v.passed for k, v in report.results.items()},
        }
