#!/usr/bin/env python3
"""skillos.cswdp.survival_fund — 生存保障金计算引擎

两笔钱分账（2026-10-24 修订，替代 v0.6.0 单公式）:

  无条件基础 = 当地月最低工资 × 1.5                     → survival 账户（地板）
  绩效奖金   = 基础 × (历史贡献度×0.4 + 成功率×0.3 + 治理参与×0.3)
                                                        → ceiling 账户（天花板）
  绩效奖金上限 = 基础 × 2.0（即合计不超过 基础 × 3.0）

设计理由：地板不得以任何绩效指标为条件。旧公式把贡献加成并入同一个
``total_amount``，在纸面上满足无条件性，运行时不满足——零贡献者拿到的钱
低于平均值，地板退化为低利害计分。修订后两笔钱走两个账户、两套规则：
基础不可申诉（人人都有），奖金可申诉（有争议才有仲裁）。
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
        cap_multiplier: 合计上限倍数（默认 3.0）；绩效奖金上限 = 基础 × (cap_multiplier - 1)
        base_multiplier: 无条件基础倍数（默认 1.5）
    """

    FLOOR_ACCOUNT = "survival"
    CEILING_ACCOUNT = "ceiling"

    def __init__(
        self,
        local_min_wage: float = 1000.0,
        contribution_weight: float = 0.4,
        success_weight: float = 0.3,
        governance_weight: float = 0.3,
        cap_multiplier: float = 3.0,
        base_multiplier: float = 1.5,
    ) -> None:
        if cap_multiplier < 1.0:
            raise ValueError("cap_multiplier must be >= 1.0 (floor cannot be capped away)")
        if base_multiplier <= 0.0:
            raise ValueError("base_multiplier must be > 0")
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
        include_performance_bonus: bool = True,
    ) -> SurvivalFundRecord:
        issues: list[str] = []

        contribution = self._clamp_factor(historical_contribution, "contribution", issues)
        success = self._clamp_factor(skill_success_rate, "skill_success_rate", issues)
        governance = self._clamp_factor(governance_participation, "governance_participation", issues)

        base = self._local_min_wage * self._base_multiplier
        bonus_cap = base * (self._cap_multiplier - 1.0)
        bonus = 0.0
        if include_performance_bonus:
            raw_bonus = base * (
                contribution * self._weights["contribution"]
                + success * self._weights["success"]
                + governance * self._weights["governance"]
            )
            bonus = min(raw_bonus, bonus_cap)

        # 无条件部分不参与任何 clamp / min / 条件分支：地板不可被绩效侵蚀。
        unconditional = base
        amount = unconditional + bonus

        factors = {
            "contribution": contribution,
            "skill_success_rate": success,
            "governance_participation": governance,
            "current_period_revenue": max(current_period_revenue, 0.0),
            "clamped": bool(issues),
            "include_performance_bonus": include_performance_bonus,
        }

        return SurvivalFundRecord(
            contributor_id=contributor_id,
            base_amount=round(base, 4),
            bonus_amount=round(bonus, 4),
            total_amount=round(amount, 4),
            unconditional_amount=round(unconditional, 4),
            performance_bonus=round(bonus, 4),
            period=self._current_period(),
            local_min_wage=self._local_min_wage,
            factors=factors,
            accounts={
                self.FLOOR_ACCOUNT: round(unconditional, 4),
                self.CEILING_ACCOUNT: round(bonus, 4),
            },
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
            "unconditional_amount": record.unconditional_amount,
            "performance_bonus": record.performance_bonus,
            "accounts": dict(record.accounts),
            "policies": {
                "floor": "unconditional (no performance condition)",
                "ceiling": "performance-linked (appealable)",
            },
            "floor_is_unconditional": record.floor_is_unconditional,
            "cap": round(record.unconditional_amount * self._cap_multiplier, 4),
            "factors": record.factors,
        }
