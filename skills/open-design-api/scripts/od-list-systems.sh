#!/bin/bash
# List available design systems
API="http://127.0.0.1:60479"
curl -s "$API/api/design-systems" | python3 -m json.tool
