#!/bin/bash
# List available skills
API="http://127.0.0.1:60479"
curl -s "$API/api/skills" | python3 -m json.tool
