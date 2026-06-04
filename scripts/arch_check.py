"""Verify all .py files in kernel/, protocol/, distribution/ map to declared layers."""

import sys
from pathlib import Path

BASE = Path(".")

DECLARED_LAYERS = {
    "kernel": "L1 内核层",
    "protocol": "L2 协议层",
    "distribution": "L3 经济层",
}

ALLOWED_ROOTS = {"kernel", "protocol", "distribution", "skills", "tests", "scripts", "docs"}
ALLOWED_SKILL_PREFIXES = {"platforms", "references", "templates", "utils", "tools", "tests", "reports"}

errors = []

for layer_dir in DECLARED_LAYERS:
    layer_path = BASE / layer_dir
    if not layer_path.is_dir():
        errors.append(f"Declared layer directory missing: {layer_dir}")
        continue
    py_files = list(layer_path.rglob("*.py"))
    if not py_files:
        errors.append(f"Layer {layer_dir} has no Python files")
        continue
    print(f"{DECLARED_LAYERS[layer_dir]}: {len(py_files)} files")

# Check for .py files outside declared layers
undocumented = []
for f in BASE.rglob("*.py"):
    parts = f.relative_to(BASE).parts
    root = parts[0] if parts else ""
    if root in ALLOWED_ROOTS:
        continue
    if root in ALLOWED_SKILL_PREFIXES:
        continue
    if root == "data" and f.name == "__init__.py":
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
