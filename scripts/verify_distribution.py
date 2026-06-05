"""Verify 5/25/70 distribution model constants and arithmetic."""

import sys
from pathlib import Path

_self = Path(__file__).resolve()
_proj_parent = _self.parent.parent.parent  # scripts/../.. = skillos root's parent
if str(_proj_parent) not in sys.path:
    sys.path.insert(0, str(_proj_parent))

from skillos.distribution.engine import (
    DistributionEngine,
    CONTRIBUTOR_SECONDARY_SPLIT,
    ECOSYSTEM_FUND_ALLOCATION,
    WEIGHT_FORMULA_COEFFICIENTS,
)

errors = []

engine = DistributionEngine()

# 5/25/70 ratio check
if abs(engine.PLATFORM_RATIO - 0.05) > 1e-9:
    errors.append(f"PLATFORM_RATIO expected 0.05, got {engine.PLATFORM_RATIO}")
if abs(engine.ECOSYSTEM_RATIO - 0.25) > 1e-9:
    errors.append(f"ECOSYSTEM_RATIO expected 0.25, got {engine.ECOSYSTEM_RATIO}")
if abs(engine.CONTRIBUTOR_RATIO - 0.70) > 1e-9:
    errors.append(f"CONTRIBUTOR_RATIO expected 0.70, got {engine.CONTRIBUTOR_RATIO}")

# Secondary split sums to 1.0
secondary_sum = sum(CONTRIBUTOR_SECONDARY_SPLIT.values())
if abs(secondary_sum - 1.0) > 1e-9:
    errors.append(f"CONTRIBUTOR_SECONDARY_SPLIT sums to {secondary_sum}, expected 1.0")
if set(CONTRIBUTOR_SECONDARY_SPLIT.keys()) != {"creator", "worker", "referrer", "platform", "community"}:
    errors.append("CONTRIBUTOR_SECONDARY_SPLIT keys mismatch")

# Ecosystem fund sums to 0.25
eco_sum = sum(ECOSYSTEM_FUND_ALLOCATION.values())
if abs(eco_sum - 0.25) > 1e-9:
    errors.append(f"ECOSYSTEM_FUND_ALLOCATION sums to {eco_sum}, expected 0.25")

# Weight coefficients sum to 1.0
weight_sum = sum(WEIGHT_FORMULA_COEFFICIENTS.values())
if abs(weight_sum - 1.0) > 1e-9:
    errors.append(f"WEIGHT_FORMULA_COEFFICIENTS sums to {weight_sum}, expected 1.0")
if set(WEIGHT_FORMULA_COEFFICIENTS.keys()) != {"historical_contribution", "current_attribution", "success_rate", "governance_participation"}:
    errors.append("WEIGHT_FORMULA_COEFFICIENTS keys mismatch")

# Single $1.00 distribution arithmetic
from skillos._types import SkillCall
call = SkillCall(skill_id="test", caller_id="test", input_data={}, revenue_usd=1.0)
record = engine.distribute(call)
platform_expected = 0.05
eco_expected = 0.25
contributor_expected = 0.70
if abs(record.platform_fee - platform_expected) > 1e-6:
    errors.append(f"platform_fee expected {platform_expected}, got {record.platform_fee}")
if abs(record.ecosystem_fee - eco_expected) > 1e-6:
    errors.append(f"ecosystem_fee expected {eco_expected}, got {record.ecosystem_fee}")
if abs(record.contributor_pool - contributor_expected) > 1e-6:
    errors.append(f"contributor_pool expected {contributor_expected}, got {record.contributor_pool}")

if errors:
    for e in errors:
        print(f"FAIL: {e}")
    sys.exit(1)
else:
    print("PASS: Distribution model verified")
