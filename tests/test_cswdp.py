"""Tests for skillos.cswdp — CSWDP (Carbon-Silicon Wisdom Dividend Protocol)"""

import pytest

from skillos.cswdp import (
    CostCircuitBreaker,
    QualityCheckResult,
    QualityGate,
    QualityReport,
    SurvivalFundCalculator,
)
from skillos.cswdp.cost_circuit import CostCircuitSnapshot
from skillos.cswdp.models import SurvivalFundRecord

# ---------------------------------------------------------------------------
# SurvivalFundCalculator
# ---------------------------------------------------------------------------


class TestSurvivalFund:
    def test_baseline_no_contribution(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate(
            contributor_id="c1",
            historical_contribution=0.0,
            current_period_revenue=0.0,
            skill_success_rate=0.0,
            governance_participation=0.0,
        )
        assert isinstance(rec, SurvivalFundRecord)
        assert rec.base_amount == 1500.0
        assert rec.bonus_amount == 0.0
        assert rec.total_amount == 1500.0

    def test_contribution_bonus(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate(
            contributor_id="c1",
            historical_contribution=1.0,
            current_period_revenue=0.0,
            skill_success_rate=1.0,
            governance_participation=1.0,
        )
        # bonus = 1500 * (0.4 + 0.3 + 0.3) = 1500 * 1.0 = 1500
        assert rec.bonus_amount == 1500.0
        # total = 1500 + 1500 = 3000 (below cap 4500)
        assert rec.total_amount == 3000.0

    def test_cap_enforced(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate(
            contributor_id="c1",
            historical_contribution=1.0,
            current_period_revenue=0.0,
            skill_success_rate=1.0,
            governance_participation=1.0,
        )
        assert rec.total_amount <= 4500.0

    def test_factor_clamping(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate(
            contributor_id="c1",
            historical_contribution=1.5,
            current_period_revenue=-5.0,
            skill_success_rate=2.0,
            governance_participation=-0.5,
        )
        assert rec.factors["contribution"] == 1.0
        assert rec.factors["skill_success_rate"] == 1.0
        assert rec.factors["governance_participation"] == 0.0
        assert rec.factors["current_period_revenue"] == 0.0
        # contribution=1.0, success=1.0, governance=0.0 (clamped)
        # bonus = 1500 * (0.4 + 0.3 + 0.0) = 1050; total = 1500 + 1050 = 2550
        assert rec.total_amount == 2550.0

    def test_describe_contains_audit_fields(self):
        calc = SurvivalFundCalculator(local_min_wage=800.0)
        rec = calc.calculate(
            contributor_id="c1",
            historical_contribution=0.5,
            current_period_revenue=10.0,
            skill_success_rate=0.8,
            governance_participation=0.2,
        )
        desc = calc.describe(rec)
        assert desc["contributor_id"] == "c1"
        assert desc["local_min_wage"] == 800.0
        assert desc["total_amount"] == rec.total_amount
        assert "cap" in desc
        assert "factors" in desc

    def test_period_format(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate("c1", 0.0, 0.0, 0.0, 0.0)
        assert "-" in rec.period
        assert len(rec.period.split("-")) == 2

    # -- 地板与天花板分账（2026-10-24） --------------------------------------

    def test_floor_unconditional_when_all_factors_zero(self):
        """零贡献者的地板必须与满贡献者的地板完全相同。"""
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        zero = calc.calculate("zero", 0.0, 0.0, 0.0, 0.0)
        full = calc.calculate("full", 1.0, 0.0, 1.0, 1.0)
        assert zero.unconditional_amount == 1500.0
        assert full.unconditional_amount == 1500.0
        assert zero.unconditional_amount == full.unconditional_amount
        assert zero.floor_is_unconditional is True

    def test_floor_invariant_under_extreme_factors(self):
        calc = SurvivalFundCalculator(local_min_wage=1200.0)
        for factors in [
            (0.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (-3.0, 9.0, -0.2),
            (0.3, 0.0, 0.7),
        ]:
            rec = calc.calculate("c1", factors[0], 0.0, factors[1], factors[2])
            assert rec.unconditional_amount == 1800.0
            assert rec.base_amount == rec.unconditional_amount

    def test_bonus_isolated_in_ceiling_account(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate("c1", 0.5, 0.0, 0.5, 0.5)
        assert rec.accounts["survival"] == rec.unconditional_amount
        assert rec.accounts["ceiling"] == rec.performance_bonus
        assert rec.accounts["survival"] + rec.accounts["ceiling"] == rec.total_amount

    def test_disable_performance_bonus_keeps_floor(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate("c1", 1.0, 0.0, 1.0, 1.0, include_performance_bonus=False)
        assert rec.unconditional_amount == 1500.0
        assert rec.performance_bonus == 0.0
        assert rec.total_amount == 1500.0
        assert rec.factors["include_performance_bonus"] is False

    def test_bonus_cap_never_touches_floor(self):
        calc = SurvivalFundCalculator(
            local_min_wage=1000.0,
            contribution_weight=1.0,
            success_weight=1.0,
            governance_weight=1.0,
        )
        rec = calc.calculate("c1", 1.0, 0.0, 1.0, 1.0)
        # raw bonus = 1500 * 3.0 = 4500，按 cap_multiplier=3.0 截到 3000
        assert rec.performance_bonus == 3000.0
        assert rec.unconditional_amount == 1500.0
        assert rec.total_amount == 4500.0
        assert rec.floor_is_unconditional is True

    def test_cap_multiplier_below_one_rejected(self):
        with pytest.raises(ValueError):
            SurvivalFundCalculator(cap_multiplier=0.5)

    def test_describe_declares_account_policies(self):
        calc = SurvivalFundCalculator(local_min_wage=1000.0)
        rec = calc.calculate("c1", 0.2, 0.0, 0.2, 0.2)
        desc = calc.describe(rec)
        assert desc["policies"]["floor"].startswith("unconditional")
        assert desc["policies"]["ceiling"].startswith("performance")
        assert desc["accounts"]["survival"] == desc["unconditional_amount"]
        assert desc["floor_is_unconditional"] is True


# ---------------------------------------------------------------------------
# CostCircuitBreaker
# ---------------------------------------------------------------------------


class TestCostCircuit:
    def test_normal_allow(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        decision = breaker.check(1.0)
        assert decision["allowed"] is True
        assert decision["mode"] == "NORMAL"

    def test_zero_budget_rejected(self):
        with pytest.raises(ValueError):
            CostCircuitBreaker(daily_budget_usd=0.0)

    def test_negative_estimated_cost_rejected(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        with pytest.raises(ValueError):
            breaker.check(-1.0)

    def test_paused_when_budget_exhausted(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        breaker.record_spend(99.0)
        decision = breaker.check(0.5)
        assert decision["allowed"] is False
        assert decision["mode"] == "PAUSED"
        assert decision["reason"] == "budget_exhausted"

    def test_low_mode_above_threshold(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        breaker.record_spend(75.0)  # remaining 25% -> LOW but allowed
        decision = breaker.check(0.5)
        assert decision["mode"] == "LOW"
        assert decision["allowed"] is True

    def test_critical_blocked_above_ratio(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        breaker.record_spend(95.0)  # remaining 5% -> CRITICAL
        decision = breaker.check(3.0)  # > 2% of budget
        assert decision["mode"] == "CRITICAL"
        assert decision["allowed"] is False
        assert decision["reason"] == "cost_too_high"

    def test_critical_allows_small_cost(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        breaker.record_spend(95.0)
        decision = breaker.check(0.5)  # <= 2% of budget
        assert decision["mode"] == "CRITICAL"
        assert decision["allowed"] is True

    def test_spend_exceeding_budget_rejected(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        decision = breaker.check(150.0)
        assert decision["allowed"] is False
        assert decision["reason"] == "cost_exceeds_daily_budget"

    def test_negative_spend_rejected(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        with pytest.raises(ValueError):
            breaker.record_spend(-5.0)

    def test_status_snapshot(self):
        breaker = CostCircuitBreaker(daily_budget_usd=100.0)
        breaker.record_spend(50.0)
        status = breaker.status()
        assert isinstance(status, CostCircuitSnapshot)
        assert status.remaining_pct == 0.5
        assert status.mode == "NORMAL"


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------


class TestQualityGate:
    def test_check_result_dataclass(self):
        result = QualityCheckResult(
            name="ruff",
            command="ruff check .",
            passed=True,
            duration_sec=0.1,
            output_tail="ok",
        )
        assert result.passed is True

    def test_run_named_unknown(self):
        gate = QualityGate(checks={"foo": ["bar"]})
        report = gate.run_named("foo")
        result = report.results["foo"]
        # bar binary likely absent -> fails cleanly rather than raising
        assert isinstance(result, QualityCheckResult)

    def test_run_all_returns_report(self):
        gate = QualityGate(checks={"true_cmd": ["/usr/bin/true"]})
        report = gate.run_all()
        assert isinstance(report, QualityReport)
        assert "true_cmd" in report.results
        assert report.passed is True

    def test_parse_coverage(self):
        report = QualityReport()
        report.results["pytest"] = QualityCheckResult(
            name="pytest",
            command="pytest",
            passed=True,
            duration_sec=0.1,
            output_tail="tests=100 ... TOTAL 92%",
        )
        gate = QualityGate()
        assert gate.parse_coverage(report) == 0.92

    def test_evaluate_coverage_threshold_fail(self):
        report = QualityReport()
        report.results["pytest"] = QualityCheckResult(
            name="pytest",
            command="pytest",
            passed=True,
            duration_sec=0.1,
            output_tail="TOTAL 50%",
        )
        gate = QualityGate()
        evaluation = gate.evaluate(report)
        assert evaluation["passed"] is False
        assert evaluation["coverage"] == 0.50

    def test_evaluate_missing_pytest_ok(self):
        report = QualityReport()
        report.results["ruff"] = QualityCheckResult(
            name="ruff",
            command="ruff",
            passed=True,
            duration_sec=0.1,
            output_tail="ok",
        )
        gate = QualityGate()
        evaluation = gate.evaluate(report)
        assert evaluation["passed"] is True


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestAPIRouter:
    def test_router_registered(self):
        from skillos.cswdp.api import router

        routes = {r.path for r in router.routes}
        assert "/cswdp/survival-fund/calculate" in routes
        assert "/cswdp/cost-circuit/check" in routes
        assert "/cswdp/cost-circuit/status" in routes
        assert "/cswdp/quality-gate/run" in routes


class TestAppMount:
    def test_cswdp_mounted(self):
        from fastapi.testclient import TestClient

        from skillos.app import create_app

        app = create_app()
        client = TestClient(app)
        resp = client.post(
            "/cswdp/survival-fund/calculate",
            json={
                "contributor_id": "t1",
                "historical_contribution": 0.5,
                "current_period_revenue": 10.0,
                "skill_success_rate": 0.9,
                "governance_participation": 0.1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["record"]["contributor_id"] == "t1"
        assert body["record"]["total_amount"] > 0

    def test_survival_fund_floor_only_via_api(self):
        from fastapi.testclient import TestClient

        from skillos.app import create_app

        client = TestClient(create_app())
        resp = client.post(
            "/cswdp/survival-fund/calculate",
            json={
                "contributor_id": "t2",
                "historical_contribution": 1.0,
                "skill_success_rate": 1.0,
                "governance_participation": 1.0,
                "local_min_wage": 1000.0,
                "include_performance_bonus": False,
            },
        )
        assert resp.status_code == 200
        record = resp.json()["record"]
        assert record["unconditional_amount"] == 1500.0
        assert record["performance_bonus"] == 0.0
        assert record["total_amount"] == 1500.0
        assert record["floor_is_unconditional"] is True
