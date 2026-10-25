#!/bin/bash
# =============================================================================
# sanitize-for-push.sh — 发布前内容安全检查（T3/T2 泄露）
#
# 用法:
#   bash scripts/sanitize-for-push.sh
#   SKILLOS_SANITIZE_ROOT=/tmp/fixture bash scripts/sanitize-for-push.sh
#
# 默认扫描范围：git 已跟踪的全部文件（仓库根、skillos/、skills/、
# skillos-contrib/、audit_logs/、pyproject.toml 等），不再依赖目录白名单。
# SKILLOS_SANITIZE_ROOT 用于负向测试/离线目录扫描。
#
# 检查项:
#   1. 绝对路径泄露 (/Volumes/, /Users/<x>/, file:///)
#   2. 组织名/内部代号引用（警告，不阻断）
#   3. 专有文件名泄露 (SOUL.md, IDENTITY.md, .openclaw/ ...)
#   4. API Key / 私钥泄露
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCAN_ROOT="${SKILLOS_SANITIZE_ROOT:-$REPO_ROOT}"
FAILED=0

if [ -z "${SKILLOS_SANITIZE_ROOT:-}" ]; then
    cd "$REPO_ROOT"
fi

echo "🔍 发布前内容安全检查"
echo "   扫描根: $SCAN_ROOT"
echo "   模式: $([ -n "${SKILLOS_SANITIZE_ROOT:-}" ] && echo directory || echo 'git tracked files')"
echo ""

# 规则文件自身包含检测模式串，必须豁免（与旧版 pre-push 行为一致）。
RULE_EXCLUDES=(
    ':(exclude)scripts/sanitize-for-push.sh'
    ':(exclude)scripts/check_staged_leaks.py'
    ':(exclude).pre-commit-config.yaml'
    ':(exclude).github/'
)

scan() {
    local pattern="$1"
    local extra="${2:-}"
    if [ -n "${SKILLOS_SANITIZE_ROOT:-}" ]; then
        grep -RInE "$pattern" "$SCAN_ROOT" \
            --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=.venv \
            --exclude-dir=.mypy_cache --exclude-dir=.ruff_cache --exclude-dir=.pytest_cache \
            2>/dev/null || true
    else
        if [ -n "$extra" ]; then
            git grep -nE "$pattern" -- . "$extra" "${RULE_EXCLUDES[@]}" 2>/dev/null || true
        else
            git grep -nE "$pattern" -- . "${RULE_EXCLUDES[@]}" 2>/dev/null || true
        fi
    fi
}

# ── Check 1: 绝对路径泄露 ──────────────────────────────────────────
echo "─── 检查 1: 绝对路径泄露 ───"
ABSOLUTE_PATTERN='(/Volumes/|/Users/[A-Za-z]/|file:///(Volumes|Users|home|root|private|mnt)/)'
ABSOLUTE_MATCHES=$(scan "$ABSOLUTE_PATTERN")

if [ -n "$ABSOLUTE_MATCHES" ]; then
    COUNT=$(echo "$ABSOLUTE_MATCHES" | wc -l | tr -d ' ')
    echo -e "${RED}❌ 发现 $COUNT 处绝对路径泄露${NC}"
    echo "$ABSOLUTE_MATCHES" | head -20
    FAILED=1
else
    echo -e "${GREEN}✅ 无绝对路径泄露${NC}"
fi

# ── Check 1b: 符号链接指向 ──────────────────────────────────────────
echo ""
echo "─── 检查 1b: 符号链接指向 ───"
if [ -n "${SKILLOS_SANITIZE_ROOT:-}" ]; then
    SYMLINK_MATCHES=$(find "$SCAN_ROOT" -type l 2>/dev/null | while IFS= read -r link; do
        target=$(readlink "$link" 2>/dev/null || true)
        if [[ "$target" == /* ]]; then echo "$link -> $target"; fi
    done)
else
    SYMLINK_MATCHES=$(git ls-files -s | while IFS=$'\t' read -r meta path; do
        if [[ "$meta" == 120000* ]]; then
            target=$(readlink "$path" 2>/dev/null || true)
            if [[ "$target" == /* ]]; then echo "$path -> $target"; fi
        fi
    done)
fi

if [ -n "$SYMLINK_MATCHES" ]; then
    COUNT=$(echo "$SYMLINK_MATCHES" | wc -l | tr -d ' ')
    echo -e "${RED}❌ 发现 $COUNT 个指向绝对路径的符号链接${NC}"
    echo "$SYMLINK_MATCHES" | head -10
    FAILED=1
else
    echo -e "${GREEN}✅ 无绝对路径符号链接${NC}"
fi

# ── Check 2: 组织名/内部代号 ───────────────────────────────────────
echo ""
echo "─── 检查 2: 组织名/内部代号引用 ───"
ORG_PATTERN='(openclaw|maref-org|frankiehot|athena-governance|clawra)'
ORG_MATCHES=$(scan "$ORG_PATTERN")

if [ -n "$ORG_MATCHES" ]; then
    COUNT=$(echo "$ORG_MATCHES" | wc -l | tr -d ' ')
    echo -e "${YELLOW}⚠️  发现 $COUNT 处组织名/内部代号引用（警告，不阻断）${NC}"
    echo "$ORG_MATCHES" | head -10
else
    echo -e "${GREEN}✅ 无组织名泄露${NC}"
fi

# ── Check 3: 专有文件名泄露 ────────────────────────────────────────
echo ""
echo "─── 检查 3: 专有文件名泄露 ───"
PROPRIETARY_FILES=$(find "$SCAN_ROOT" -maxdepth 3 \
    \( -name "SOUL.md" -o -name "IDENTITY.md" -o -name "HEARTBEAT.md" \
    -o -name "TOOLS.md" -o -name "USER.md" -o -path "*/.openclaw/*" \) \
    -not -path "*/.git/*" -not -path "*/.venv/*" \
    2>/dev/null || true)

if [ -n "$PROPRIETARY_FILES" ]; then
    echo -e "${RED}❌ 发现专有文件:${NC}"
    echo "$PROPRIETARY_FILES"
    FAILED=1
else
    echo -e "${GREEN}✅ 无专有文件${NC}"
fi

# ── Check 4: API Key / 私钥泄露 ────────────────────────────────────
echo ""
echo "─── 检查 4: API Key / 私钥泄露 ───"
KEY_MATCHES=$(scan '(sk-[A-Za-z0-9]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' ':(exclude)tests/')

if [ -n "$KEY_MATCHES" ]; then
    COUNT=$(echo "$KEY_MATCHES" | wc -l | tr -d ' ')
    echo -e "${RED}❌ 发现 $COUNT 处可能的密钥泄露!${NC}"
    echo "$KEY_MATCHES" | head -10
    FAILED=1
else
    echo -e "${GREEN}✅ 无 API Key/私钥泄露${NC}"
fi

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "─── 检查完成 ───"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ 全部检查通过，可以安全推送${NC}"
else
    echo -e "${RED}❌ 存在需修复的问题，请先处理后再推送${NC}"
    exit 1
fi
