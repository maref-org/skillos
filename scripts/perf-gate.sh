#!/usr/bin/env bash
# SkillOS 性能门禁 — 在 CI 中运行 k6 压测并检查阈值
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
REPORT_FILE="${2:-k6-report.json}"

echo "==> Running k6 load test against ${BASE_URL}"

k6 run \
  --out json="${REPORT_FILE}" \
  -e "BASE_URL=${BASE_URL}" \
  scripts/load-test.js

echo "==> Checking performance thresholds"
THRESHOLD_FAILURES=$(python3 -c "
import json
with open('${REPORT_FILE}') as f:
    results = json.load(f)
checks = results.get('metrics', {}).get('checks', {})
fails = checks.get('fails', 0)
print(fails)
")

if [ "${THRESHOLD_FAILURES}" -gt 0 ]; then
  echo "❌ Performance gate FAILED: ${THRESHOLD_FAILURES} threshold violations"
  python3 -c "
import json
with open('${REPORT_FILE}') as f:
    print(f.read())
" | head -50
  exit 1
fi

echo "✅ Performance gate PASSED"
