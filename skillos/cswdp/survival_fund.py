#!/usr/bin/env python3
"""skillos.cswdp.survival_fund — 生存保障金计算引擎

公式（roadmap §5.2.2）:
  基础保障 = 当地最低工资 × 1.5
  贡献加成 = 基础保障 × (历史贡献度 × 0.4 + 成功率 × 0.3 + 治理参与 × 0.3)
  总保障金 = min(基础保障 + 贡献加成, 基础保障 × 3.0)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from skillos.cswdp.models import SurvivalFundRecord


class SurvivalFundCalculator:
    """生存保障金计算引擎

    参数:
        local_min_wage: 当地月最低工资（USD）
        contribution_weight: 历史贡献度权重（默认 0.4）
        success_weight: 技能成功率权重（默认 0.3）
        governance_weight: 治理参与度权重（默认 0.3）
        cap_multiplier: 上限倍数（默认 3.0）
        base_multiplier: 基础保障倍数（默认 1.5）
    """

    def __init__(
        self,
        local_min_wage: float = 1000.0,
        contribution_weight: float = 0.4,
        success_weight: float = 0.3,
        governance_weight: float = 0.3,
        cap_multiplier: float = 3.0,
        base_multiplier: float = 1.5,
    ) -> None:
        self._local_min_wage = local_min_wage
        self._weights = {
            "contribution": contribution_weight,
            "success": success_weight,
            "governance": governance_weight,
        }
        self._cap_multiplier = cap_multiplier
        self._base_multiplier = base_multiplier

    def _current_period(self) -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"

    @staticmethod
    def _clamp_factor(value: float, name: str, issues: list[str]) -> float:
        if value < 0.0:
            issues.append(f"{name} clamped from {value} to 0.0")
            return 0.0
        if value > 1.0:
            issues.append(f"{name} clamped from {value} to 1.0")
            return 1.0
        return value

    def calculate(
        self,
        contributor_id: str,
        historical_contribution: float,
        current_period_revenue: float,
        skill_success_rate: float,
        governance_participation: float,
    ) -> SurvivalFundRecord:
        issues: list[str] = []

        contribution = self._clamp_factor(historical_contribution, "contribution", issues)
        success = self._clamp_factor(skill_success_rate, "skill_success_rate", issues)
        governance = self._clamp_factor(governance_participation, "governance_participation", issues)

        base = self._local_min_wage * self._base_multiplier
        bonus = base * (
            contribution * self._weights["contribution"]
            + success * self._weights["success"]
            + governance * self._weights["governance"]
        )
        amount = min(base + bonus, base * self._cap_multiplier)

        factors = {
            "contribution": contribution,
            "skill_success_rate": success,
            "governance_participation": governance,
            "current_period_revenue": max(current_period_revenue, 0.0),
            "clamped": bool(issues),
        }

        return SurvivalFundRecord(
            contributor_id=contributor_id,
            base_amount=round(base, 4),
            bonus_amount=round(bonus, 4),
            total_amount=round(amount, 4),
            period=self._current_period(),
            local_min_wage=self._local_min_wage,
            factors=factors,
        )

    def describe(self, record: SurvivalFundRecord) -> dict[str, Any]:
        """输出可审计的计算明细"""
        return {
            "contributor_id": record.contributor_id,
            "period": record.period,
            "local_min_wage": record.local_min_wage,
            "base_multiplier": self._base_multiplier,
            "weights": dict(self._weights),
            "base_amount": record.base_amount,
            "bonus_amount": record.bonus_amount,
            "total_amount": record.total_amount,
            "cap": round(record.base_amount * self._cap_multiplier, 4),
            "factors": record.factors,
        }
