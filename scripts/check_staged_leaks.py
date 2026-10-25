#!/usr/bin/env python3
"""pre-commit 内容检查：扫描本次暂存文件中的 T3 泄露与密钥（跨平台）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_VOLUME = "/Vol" + "umes/"
_USERS = "/Us" + "ers/[A-Za-z]/"
_FILE_URL = "file:///" + "(?:Vol" + "umes|Us" + "ers|home|root|private|mnt)/"
_API_KEY = "s" + "k-" + "[A-Za-z0-9]{20,}"
_PRIVATE_KEY = "BEGIN " + "(?:RSA |EC |OPENSSH )?" + "PRIVATE KEY"
_ORG = "open" + "claw" + "|maref-org|frankiehot|clawra"

BLOCKING_PATTERNS = [
    (re.compile(_VOLUME), "absolute_volume_path"),
    (re.compile(_USERS), "absolute_home_path"),
    (re.compile(_FILE_URL), "file_url"),
    (re.compile(_API_KEY), "api_key"),
    (re.compile(_PRIVATE_KEY), "private_key"),
]

WARN_PATTERNS = [
    (re.compile(_ORG), "org_name"),
]

IGNORED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".pdf", ".zip", ".whl"}

RULE_FILES = {
    "scripts/sanitize-for-push.sh",
    "scripts/check_staged_leaks.py",
    ".pre-commit-config.yaml",
}


def _is_rule_file(path: Path) -> bool:
    normalized = path.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized in RULE_FILES or normalized.startswith(".github/") or normalized.startswith("audit_logs/")


def main(argv: list[str]) -> int:
    failures = 0
    for raw in argv:
        path = Path(raw)
        if not path.is_file() or path.suffix.lower() in IGNORED_SUFFIXES or _is_rule_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        normalized = path.as_posix()
        if normalized.startswith("./"):
            normalized = normalized[2:]
        is_test_fixture = normalized.startswith("tests/")
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in BLOCKING_PATTERNS:
                if is_test_fixture and label in {"api_key", "private_key"}:
                    continue
                if pattern.search(line):
                    print(f"{path}:{lineno}: [{label}] {line.strip()[:160]}")
                    failures += 1
            for pattern, label in WARN_PATTERNS:
                if pattern.search(line):
                    print(f"WARN {path}:{lineno}: [{label}] {line.strip()[:120]}")
    if failures:
        print(f"\nT3/T2 leak check failed: {failures} finding(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
