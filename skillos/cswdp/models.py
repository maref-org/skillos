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
    """生存保障金记录。

    两笔钱分账的硬性区分（地板与天花板不得混同）:

    - ``unconditional_amount`` / ``base_amount``: 无条件基础，人人可得，
      不与任何绩效指标挂钩，走 ``survival`` 账户。任何因子为 0 时该金额不变。
    - ``performance_bonus`` / ``bonus_amount``: 绩效奖金，按贡献度/成功率/治理
      参与计发，走 ``ceiling`` 账户。它可以为 0，且不得成为生存的唯一来源。

    ``total_amount`` 为两账户合计，仅为兼容与对账保留，不是可挂钩指标。
    """

    contributor_id: str = ""
    base_amount: float = 0.0
    bonus_amount: float = 0.0
    total_amount: float = 0.0
    unconditional_amount: float = 0.0
    performance_bonus: float = 0.0
    period: str = ""
    local_min_wage: float = 0.0
    factors: dict[str, float] = field(default_factory=dict)
    accounts: dict[str, float] = field(default_factory=dict)
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_utc_now)

    @property
    def floor_is_unconditional(self) -> bool:
        """地板是否保持无条件：无条件部分必须等于基础保障且不随因子变动。"""
        return self.unconditional_amount == self.base_amount and self.base_amount >= 0.0


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
