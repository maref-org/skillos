#!/bin/bash
# List available plugins
API="http://127.0.0.1:60479"
curl -s "$API/api/plugins" | python3 -m json.tool
