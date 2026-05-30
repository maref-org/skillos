#!/bin/bash
# Open Design Health Check
set -e
API="http://127.0.0.1:60479"

echo "Checking Open Design daemon..."
echo ""

# Health
echo "=== Health ==="
curl -s "$API/api/health" | python3 -m json.tool 2>/dev/null || echo "  UNREACHABLE"
echo ""

# Version
echo "=== Version ==="
curl -s "$API/api/version" | python3 -m json.tool 2>/dev/null || echo "  UNREACHABLE"
echo ""

# Daemon Status
echo "=== Daemon Status ==="
curl -s "$API/api/daemon/status" | python3 -m json.tool 2>/dev/null || echo "  UNREACHABLE"
