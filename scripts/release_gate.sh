#!/bin/bash
# =============================================================================
# release_gate.sh — 单一发布门禁入口（本地 / CI 同一口径）
#
# 用法:
#   bash scripts/release_gate.sh
#   SKIP_AUDIT=1 bash scripts/release_gate.sh   # 跳过依赖审计（离线环境）
#
# 退出码 0 = 全部通过；非 0 = 任一检查失败。
# 依赖: pip install -e ".[dev,web]"
# =============================================================================

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VENV_BIN="$REPO_ROOT/.venv/bin"
if [ -x "$VENV_BIN/python" ]; then
    PY="$VENV_BIN/python"
    BIN="$VENV_BIN"
else
    PY="$(command -v python3)"
    BIN="$(dirname "$PY")"
fi

FAILED=0
STEP=0

run() {
    local name="$1"
    shift
    STEP=$((STEP + 1))
    printf '\n[%02d] %s\n' "$STEP" "$name"
    if "$@"; then
        echo "PASS: $name"
    else
        echo "FAIL: $name"
        FAILED=1
    fi
}

run "ruff check" "$BIN/ruff" check .
run "ruff format check" "$BIN/ruff" format --check skillos/ scripts/
run "mypy" "$BIN/mypy"
run "bandit" "$BIN/bandit" -r skillos/ -c pyproject.toml --severity-level medium
run "pytest + coverage" "$PY" -m pytest tests/ -q --cov=skillos --cov-fail-under=80
run "verify_distribution" "$PY" scripts/verify_distribution.py
run "arch_check" "$PY" scripts/arch_check.py
run "verify_kb_sync" "$PY" scripts/verify_kb_sync.py
run "governance sanitize" bash scripts/sanitize-for-push.sh
run "meta_monitor M0-M3" "$PY" scripts/meta_monitor.py --check M0,M1,M2,M3

if [ "${SKIP_AUDIT:-0}" != "1" ]; then
    run "pip-audit" "$BIN/pip-audit" --skip-editable \
        --ignore-vuln GHSA-537c-gmf6-5ccf \
        --ignore-vuln GHSA-6v7p-g79w-8964
fi

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "RELEASE GATE: PASS"
    exit 0
fi
echo "RELEASE GATE: FAIL"
exit 1
