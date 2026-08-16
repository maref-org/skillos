#!/usr/bin/env python3
"""skillos.cswdp.models — CSWDP (Carbon-Silicon Wisdom Dividend Protocol) 数据模型

功能:
  - 生存保障金记录（SurvivalFundRecord）
  - 成本熔断状态快照（CostCircuitSnapshot）
  - 质量门禁报告（QualityReport）
"""

import uuid
from dataclasses import dataclass, field
from typing import Any


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class SurvivalFundRecord:
    contributor_id: str = ""
    base_amount: float = 0.0
    bonus_amount: float = 0.0
    total_amount: float = 0.0
    period: str = ""
    local_min_wage: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_utc_now)


@dataclass
class CostCircuitSnapshot:
    mode: str = "NORMAL"
    allowed: bool = True
    remaining_pct: float = 1.0
    reason: str = ""
    daily_budget_usd: float = 5.0
    spent_today: float = 0.0
    estimated_cost: float = 0.0
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_utc_now)


@dataclass
class QualityCheckResult:
    name: str = ""
    command: str = ""
    passed: bool = False
    duration_sec: float = 0.0
    output_tail: str = ""


@dataclass
class QualityReport:
    results: dict[str, QualityCheckResult] = field(default_factory=dict)
    passed: bool = False
    coverage: float = 0.0
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_utc_now)

    def summary(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": {k: v.passed for k, v in self.results.items()},
            "coverage": self.coverage,
            "created_at": self.created_at,
        }
