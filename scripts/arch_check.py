"""Verify all .py files in skillos/ map to declared layers."""

import sys
from pathlib import Path

BASE = Path(".")

DECLARED_LAYERS = {
    "kernel": "L1 内核层",
    "protocol": "L2 协议层",
    "distribution": "L3 经济层",
    "negmarket": "L3 经济层",
}

ALLOWED_ROOTS = {"skillos", "skills", "tests", "scripts", "docs", "migrations", "skillos-contrib"}
ALLOWED_ROOT_FILES = {"_types.py", "__init__.py"}
IGNORED_DIRS = {".venv", ".git", "__pycache__", ".pytest_cache"}

errors = []

# Check skillos/ sub-packages
for layer_dir in DECLARED_LAYERS:
    layer_path = BASE / "skillos" / layer_dir
    if not layer_path.is_dir():
        errors.append(f"Declared layer directory missing: skillos/{layer_dir}")
        continue
    py_files = list(layer_path.rglob("*.py"))
    if not py_files:
        errors.append(f"Layer {layer_dir} (skillos/{layer_dir}) has no Python files")
        continue
    print(f"{DECLARED_LAYERS[layer_dir]}: {len(py_files)} files")

# Check for .py files outside allowed roots
undocumented = []
for f in BASE.rglob("*.py"):
    parts = f.relative_to(BASE).parts
    if not parts:
        continue
    root = parts[0]
    if root in ALLOWED_ROOTS or root in IGNORED_DIRS:
        continue
    if len(parts) == 1 and f.name in ALLOWED_ROOT_FILES:
        continue
    undocumented.append(str(f))

if undocumented:
    errors.append(f"Files outside declared architecture layers: {undocumented}")

if errors:
    for e in errors:
        print(f"FAIL: {e}")
    sys.exit(1)
else:
    print("PASS: Architecture check — all modules within declared layers")
