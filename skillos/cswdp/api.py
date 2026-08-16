#!/usr/bin/env python3
"""skillos.cswdp.api — CSWDP FastAPI 路由

端点:
  POST /cswdp/survival-fund/calculate   计算生存保障金
  GET  /cswdp/cost-circuit/status       成本熔断状态
  POST /cswdp/cost-circuit/check        成本熔断检查
  POST /cswdp/quality-gate/run          运行质量门禁
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skillos.cswdp.cost_circuit import CostCircuitBreaker
from skillos.cswdp.quality_gate import QualityGate
from skillos.cswdp.survival_fund import SurvivalFundCalculator

router = APIRouter(tags=["CSWDP"])


class SurvivalFundRequest(BaseModel):
    contributor_id: str = Field(..., min_length=1)
    historical_contribution: float = Field(default=0.0, ge=0.0, le=1.0)
    current_period_revenue: float = Field(default=0.0, ge=0.0)
    skill_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    governance_participation: float = Field(default=0.0, ge=0.0, le=1.0)
    local_min_wage: float = Field(default=1000.0, gt=0.0)


class CostCircuitCheckRequest(BaseModel):
    estimated_cost: float = Field(..., ge=0.0)
    daily_budget_usd: float = Field(default=5.0, gt=0.0)
    spent_today: float = Field(default=0.0, ge=0.0)


@router.post("/cswdp/survival-fund/calculate")
def calculate_survival_fund(req: SurvivalFundRequest) -> dict[str, Any]:
    """计算生存保障金并返回可审计明细"""
    calculator = SurvivalFundCalculator(local_min_wage=req.local_min_wage)
    record = calculator.calculate(
        contributor_id=req.contributor_id,
        historical_contribution=req.historical_contribution,
        current_period_revenue=req.current_period_revenue,
        skill_success_rate=req.skill_success_rate,
        governance_participation=req.governance_participation,
    )
    return {"ok": True, "record": calculator.describe(record)}


@router.post("/cswdp/cost-circuit/check")
def check_cost_circuit(req: CostCircuitCheckRequest) -> dict[str, Any]:
    """检查预计成本是否可放行"""
    try:
        breaker = CostCircuitBreaker(daily_budget_usd=req.daily_budget_usd)
        breaker.record_spend(req.spent_today)
        return {"ok": True, "decision": breaker.check(req.estimated_cost)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/cswdp/cost-circuit/status")
def get_cost_circuit_status() -> dict[str, Any]:
    """获取（默认实例）成本熔断状态"""
    breaker = CostCircuitBreaker()
    status = breaker.status()
    return {
        "ok": True,
        "mode": status.mode,
        "remaining_pct": status.remaining_pct,
        "daily_budget_usd": status.daily_budget_usd,
        "spent_today": status.spent_today,
    }


@router.post("/cswdp/quality-gate/run")
def run_quality_gate(*names: str) -> dict[str, Any]:
    """运行质量门禁（默认全部检查）"""
    gate = QualityGate()
    report = gate.run_all() if not names else gate.run_named(*names)
    evaluation = gate.evaluate(report)
    return {"ok": True, "report": report.summary(), "evaluation": evaluation}
