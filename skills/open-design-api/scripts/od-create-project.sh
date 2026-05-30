#!/bin/bash
# Create a new design project
# Usage: od-create-project.sh "Project Name" [kind]
set -e
API="http://127.0.0.1:60479"

NAME="$1"
KIND="${2:-web}"

if [ -z "$NAME" ]; then
  echo "Usage: $0 \"Project Name\" [web|mobile|desktop]"
  exit 1
fi

echo "Creating project '$NAME' (kind: $KIND)..."

RESP=$(curl -s -X POST "$API/api/projects" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$NAME\", \"kind\": \"$KIND\"}")

echo "$RESP" | python3 -m json.tool
