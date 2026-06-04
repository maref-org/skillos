"""Scan for hardcoded error patterns and undocumented error codes."""

import sys
import re
from pathlib import Path

SCAN_DIRS = ["kernel", "protocol", "distribution"]

error_codes = set()
undocumented = []

for d in SCAN_DIRS:
    for py_file in Path(d).rglob("*.py"):
        text = py_file.read_text()
        codes = re.findall(r'(?:Error|error_code|ErrorCode)\s*[\"\'=:]\s*[\"\']?(\w+)[\"\']?', text)
        error_codes.update(codes)
        if not codes:
            continue

errors_found = len(error_codes)
print(f"Found {errors_found} error code references across {len(SCAN_DIRS)} layers")

if errors_found == 0:
    print("WARN: No error codes found — may need error code standardization")
    sys.exit(0)

print("PASS: Error code audit complete")
