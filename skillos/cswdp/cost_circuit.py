#!/usr/bin/env python3
"""CostCircuitBreaker — 成本熔断器

四档模式:
  NORMAL   : 剩余预算 > 30%
  LOW      : 10% ~ 30%
  CRITICAL : 2% ~ 10%   （预计成本超日预算 2% 时熔断）
  PAUSED   : < 2%       （预算耗尽，全部熔断）
"""

from __future__ import annotations

from typing import Any

from skillos.cswdp.models import CostCircuitSnapshot


class CostCircuitBreaker:
    MODES = {
        "NORMAL": (0.30, float("inf")),  # >30% 预算剩余
        "LOW": (0.10, 0.30),  # 10-30%
        "CRITICAL": (0.02, 0.10),  # 2-10%
        "PAUSED": (0.0, 0.02),  # <2%
    }

    # CRITICAL 档单次成本阈值 = 日预算 × critical_cost_ratio
    CRITICAL_COST_RATIO = 0.02

    def __init__(self, daily_budget_usd: float = 5.0) -> None:
        if daily_budget_usd <= 0:
            raise ValueError("daily_budget_usd must be positive")
        self.daily_budget = daily_budget_usd
        self.spent_today = 0.0

    def record_spend(self, amount: float) -> float:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.spent_today += amount
        return self.spent_today

    @staticmethod
    def _get_mode(remaining_pct: float) -> str:
        for mode, (lo, hi) in CostCircuitBreaker.MODES.items():
            if lo <= remaining_pct < hi:
                return mode
        return "NORMAL"

    def check(self, estimated_cost: float) -> dict[str, Any]:
        if estimated_cost < 0:
            raise ValueError("estimated_cost must be non-negative")
        if estimated_cost > self.daily_budget:
            return {
                "allowed": False,
                "mode": "CRITICAL",
                "reason": "cost_exceeds_daily_budget",
                "remaining_pct": round(1.0 - (self.spent_today / self.daily_budget), 4),
            }

        remaining_pct = 1.0 - (self.spent_today / self.daily_budget)
        mode = self._get_mode(remaining_pct)
        snapshot = CostCircuitSnapshot(
            mode=mode,
            remaining_pct=round(remaining_pct, 4),
            daily_budget_usd=self.daily_budget,
            spent_today=self.spent_today,
            estimated_cost=estimated_cost,
        )

        if mode == "PAUSED":
            snapshot.allowed = False
            snapshot.reason = "budget_exhausted"
        elif mode == "CRITICAL" and estimated_cost > self.daily_budget * self.CRITICAL_COST_RATIO:
            snapshot.allowed = False
            snapshot.reason = "cost_too_high"
        else:
            snapshot.allowed = True
            snapshot.reason = ""

        return {
            "allowed": snapshot.allowed,
            "mode": snapshot.mode,
            "reason": snapshot.reason,
            "remaining_pct": snapshot.remaining_pct,
        }

    def status(self) -> CostCircuitSnapshot:
        remaining_pct = 1.0 - (self.spent_today / self.daily_budget)
        return CostCircuitSnapshot(
            mode=self._get_mode(remaining_pct),
            remaining_pct=round(remaining_pct, 4),
            daily_budget_usd=self.daily_budget,
            spent_today=self.spent_today,
        )
