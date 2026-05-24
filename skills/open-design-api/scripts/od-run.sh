#!/bin/bash
# Create a design run and wait for completion
# Usage: od-run.sh "Your design prompt" [designSystemId]
set -e
API="http://127.0.0.1:60479"

PROMPT="$1"
DESIGN_SYSTEM="${2:-}"

if [ -z "$PROMPT" ]; then
  echo "Usage: $0 \"design prompt\" [designSystemId]"
  exit 1
fi

echo "Creating design run..."

# Build JSON body
BODY=$(python3 -c "
import json
body = {'message': '''$PROMPT'''}
if '$DESIGN_SYSTEM':
    body['designSystemId'] = '$DESIGN_SYSTEM'
print(json.dumps(body))
")

# Create run
RESP=$(curl -s -X POST "$API/api/runs" \
  -H "Content-Type: application/json" \
  -d "$BODY")

RUN_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['runId'])")
echo "Run ID: $RUN_ID"
echo ""

# Poll until complete
echo "Waiting for completion..."
while true; do
  RESP=$(curl -s "$API/api/runs/$RUN_ID")
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "  Status: $STATUS"
  if [ "$STATUS" != "running" ]; then
    break
  fi
  sleep 3
done

echo ""
echo "=== Final Response ==="
echo "$RESP" | python3 -m json.tool
