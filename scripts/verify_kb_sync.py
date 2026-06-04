"""Verify pyproject.toml version tag alignment for KB-code sync."""

import sys
import re
from pathlib import Path

errors = []

pyproject = Path("pyproject.toml").read_text()
version_match = re.search(r'version\s*=\s*"([^"]+)"', pyproject)
if not version_match:
    errors.append("No version found in pyproject.toml")
    sys.exit(1)

version = version_match.group(1)
print(f"pyproject.toml version: {version}")

readme = Path("README.md")
if readme.exists():
    text = readme.read_text()
    if version not in text:
        errors.append(f"Version {version} not mentioned in README.md")
    else:
        print("README.md: version reference found")

arch = Path("ARCHITECTURE.md")
if arch.exists():
    text = arch.read_text()
    if version not in text:
        errors.append(f"Version {version} not mentioned in ARCHITECTURE.md")
    else:
        print("ARCHITECTURE.md: version reference found")

if errors:
    for e in errors:
        print(f"FAIL: {e}")
    sys.exit(1)
else:
    print("PASS: KB-Code version sync verified")
