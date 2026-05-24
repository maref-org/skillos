#!/bin/bash
# Import a DESIGN.md file as a design system
# Usage: od-import-system.sh path/to/DESIGN.md "system-name"
set -e
API="http://127.0.0.1:60479"

FILE="$1"
NAME="$2"

if [ -z "$FILE" ] || [ -z "$NAME" ]; then
  echo "Usage: $0 path/to/DESIGN.md system-name"
  exit 1
fi

if [ ! -f "$FILE" ]; then
  echo "File not found: $FILE"
  exit 1
fi

echo "Importing design system from $FILE as '$NAME'..."

BODY=$(python3 -c "
import json
with open('$FILE', 'r') as f:
    content = f.read()
print(json.dumps({'name': '$NAME', 'body': content}))
")

RESP=$(curl -s -X POST "$API/api/design-systems/import/local" \
  -H "Content-Type: application/json" \
  -d "$BODY")

echo "$RESP" | python3 -m json.tool
