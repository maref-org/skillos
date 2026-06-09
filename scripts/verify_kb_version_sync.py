#!/usr/bin/env python3
"""Verify KB-Code version synchronization.

Scans docs/*.md for version strings and compares against pyproject.toml.
Exit code 1 if any mismatch found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VERSION_PATTERN = re.compile(r"v?(\d+\.\d+\.\d+(?:-[a-zA-Z0-9._-]+)?)")


def get_code_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    for line in pyproject.read_text().splitlines():
        line = line.strip()
        if line.startswith("version ="):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("Version not found in pyproject.toml")


def scan_docs() -> list[tuple[Path, str, str]]:
    mismatches: list[tuple[Path, str, str]] = []
    code_ver = get_code_version()
    docs_dir = REPO_ROOT / "docs"
    if not docs_dir.is_dir():
        return mismatches
    for md_file in sorted(docs_dir.rglob("*.md")):
        for i, line in enumerate(md_file.read_text().splitlines(), 1):
            for match in VERSION_PATTERN.finditer(line):
                found = match.group(1)
                if found != code_ver:
                    mismatches.append((md_file.relative_to(REPO_ROOT), str(i), found, code_ver))
    return mismatches


def main() -> int:
    code_ver = get_code_version()
    print(f"Code version: {code_ver}")
    mismatches = scan_docs()
    if not mismatches:
        print("All docs version strings match code version")
        return 0
    print(f"Found {len(mismatches)} version mismatch(es):")
    for path, line, found, expected in mismatches:
        print(f"  {path}:{line} — found '{found}', expected '{expected}'")
    return 1


if __name__ == "__main__":
    sys.exit(main())
