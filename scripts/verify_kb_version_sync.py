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

VERSION_PATTERN = re.compile(
    r"(?:\bv|\bversion[\"'\s:=]+)(\d+\.\d+\.\d+(?:-(?:beta|alpha|rc)[0-9.]*)?)",
    re.IGNORECASE,
)


def get_code_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    for line in pyproject.read_text().splitlines():
        line = line.strip()
        if line.startswith("version ="):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError("Version not found in pyproject.toml")


CURRENT_DOCS = (
    "README.md",
    "ARCHITECTURE.md",
    "docs/release-gate.md",
    "docs/01-README.md",
    "docs/04-development.md",
    "docs/06-ops.md",
    "docs/08-deployment.md",
)


def scan_docs() -> list[tuple[Path, str, str, str]]:
    """只校验声明「当前版本」的文档。

    历史计划、路线图、审计报告中的版本号属于历史事实，不参与同步校验。
    """
    mismatches: list[tuple[Path, str, str, str]] = []
    code_ver = get_code_version()
    for rel in CURRENT_DOCS:
        md_file = REPO_ROOT / rel
        if not md_file.is_file():
            continue
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
