"""Tests for skillos.distribution.engine - 5/25/70 distribution engine"""

import datetime

import pytest

from skillos.distribution.engine import (
    CONTRIBUTOR_SECONDARY_SPLIT,
    ECOSYSTEM_FUND_ALLOCATION,
    WEIGHT_FORMULA_COEFFICIENTS,
    DistributionEngine,
    SettlementPeriod,
)
from skillos.types import Contributor, SkillCall


class TestSettlementPeriod:
    def test_daily_value(self):
        assert SettlementPeriod.DAILY == "daily"

    def test_weekly_value(self):
        assert SettlementPeriod.WEEKLY == "weekly"

    def test_monthly_value(self):
        assert SettlementPeriod.MONTHLY == "monthly"

    def test_is_str_enum(self):
        assert isinstance(SettlementPeriod.DAILY, str)


class TestConstants:
    def test_ecosystem_allocation_sums_to_quarter(self):
        assert sum(ECOSYSTEM_FUND_ALLOCATION.values()) == pytest.approx(0.25, abs=1e-6)

    def test_ecosystem_allocation_keys(self):
        expected_keys = {"skill_incubation", "infrastructure", "neg_market_acquisition", "education", "risk_reserve"}
        assert set(ECOSYSTEM_FUND_ALLOCATION.keys()) == expected_keys

    def test_contributor_split_sums_to_one(self):
        assert sum(CONTRIBUTOR_SECONDARY_SPLIT.values()) == pytest.approx(1.0, abs=1e-6)

    def test_contributor_split_keys(self):
        expected_keys = {"creator", "worker", "referrer", "platform", "community"}
        assert set(CONTRIBUTOR_SECONDARY_SPLIT.keys()) == expected_keys

    def test_weight_coefficients_sums_to_one(self):
        assert sum(WEIGHT_FORMULA_COEFFICIENTS.values()) == pytest.approx(1.0, abs=1e-6)

    def test_weight_coefficients_values(self):
        assert WEIGHT_FORMULA_COEFFICIENTS["historical_contribution"] == 0.4
        assert WEIGHT_FORMULA_COEFFICIENTS["current_attribution"] == 0.3
        assert WEIGHT_FORMULA_COEFFICIENTS["success_rate"] == 0.2
        assert WEIGHT_FORMULA_COEFFICIENTS["governance_participation"] == 0.1


class TestDistributionEngineInit:
    def test_default_init(self):
        engine = DistributionEngine()
        assert engine._distribution_log == []
        assert engine._contributor_registry == {}
        assert engine._period_revenue == {}

    def test_platform_ratio(self):
        assert DistributionEngine.PLATFORM_RATIO == 0.05

    def test_ecosystem_ratio(self):
        assert DistributionEngine.ECOSYSTEM_RATIO == 0.25

    def test_contributor_ratio(self):
        assert DistributionEngine.CONTRIBUTOR_RATIO == 0.70


class TestDistributionEngineDistribute:
    def make_skill_call(self, revenue: float = 1.0, call_id: str = "call-001", skill_id: str = "skill-001"):
        return SkillCall(
            skill_id=skill_id,
            caller_id="caller-001",
            input_data={"key": "value"},
            revenue_usd=revenue,
            call_id=call_id,
        )

    def test_5_25_70_split_on_dollar(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0)
        record = engine.distribute(call)

        assert record.platform_fee == pytest.approx(0.05, abs=1e-6)
        assert record.ecosystem_fee == pytest.approx(0.25, abs=1e-6)
        assert record.contributor_pool == pytest.approx(0.70, abs=1e-6)

    def test_distribution_sums_to_total(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0)
        record = engine.distribute(call)

        total = record.platform_fee + record.ecosystem_fee + record.contributor_pool
        assert total == pytest.approx(record.total_amount, abs=1e-6)

    def test_zero_revenue(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=0.0)
        record = engine.distribute(call)

        assert record.platform_fee == 0.0
        assert record.ecosystem_fee == 0.0
        assert record.contributor_pool == 0.0

    def test_large_revenue(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=100.0)
        record = engine.distribute(call)

        assert record.platform_fee == pytest.approx(5.0, abs=1e-6)
        assert record.ecosystem_fee == pytest.approx(25.0, abs=1e-6)
        assert record.contributor_pool == pytest.approx(70.0, abs=1e-6)

    def test_ecosystem_breakdown(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0)
        record = engine.distribute(call)

        expected_breakdown = {
            key: record.ecosystem_fee * ratio
            for key, ratio in ECOSYSTEM_FUND_ALLOCATION.items()
        }
        for key, value in expected_breakdown.items():
            assert record.ecosystem_breakdown[key] == pytest.approx(value, abs=1e-6)

    def test_ecosystem_breakdown_sums_to_ecosystem_fee_times_quarter(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0)
        record = engine.distribute(call)

        total_breakdown = sum(record.ecosystem_breakdown.values())
        assert total_breakdown == pytest.approx(record.ecosystem_fee * 0.25, abs=1e-6)

    def test_secondary_distribution(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0)
        record = engine.distribute(call)

        expected = {
            role: round(record.contributor_pool * ratio, 6)
            for role, ratio in CONTRIBUTOR_SECONDARY_SPLIT.items()
        }
        for role, value in expected.items():
            assert record.secondary_distribution[role] == pytest.approx(value, abs=1e-6)

    def test_record_stored_in_log(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0)
        engine.distribute(call)

        assert len(engine.get_distribution_log()) == 1
        assert engine.get_distribution_log()[0].call_id == "call-001"

    def test_multiple_distributions(self):
        engine = DistributionEngine()
        for i in range(3):
            call = self.make_skill_call(revenue=1.0, call_id=f"call-{i}")
            engine.distribute(call)

        assert len(engine.get_distribution_log()) == 3

    def test_period_revenue_accumulates(self):
        engine = DistributionEngine()
        for _ in range(3):
            call = self.make_skill_call(revenue=1.0)
            engine.distribute(call)

        period_revenue = engine.get_period_revenue(SettlementPeriod.DAILY)
        assert period_revenue == pytest.approx(3.0, abs=1e-6)

    def test_record_fields_populated(self):
        engine = DistributionEngine()
        call = self.make_skill_call(revenue=1.0, call_id="abc-123", skill_id="skill-xyz")
        record = engine.distribute(call)

        assert record.call_id == "abc-123"
        assert record.skill_id == "skill-xyz"
        assert record.total_amount == 1.0


class TestDistributionEngineCalculateWeight:
    def test_basic_weight_calculation(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Test",
            historical_contribution=0.8,
            current_period_attribution=0.7,
            success_rate=0.9,
            governance_participation=0.5,
        )

        weight = engine.calculate_weight(contributor)
        expected = 0.4 * 0.8 + 0.3 * 0.7 + 0.2 * 0.9 + 0.1 * 0.5
        assert weight == pytest.approx(round(expected, 4), abs=1e-4)

    def test_weight_capped_at_one(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Test",
            historical_contribution=1.0,
            current_period_attribution=1.0,
            success_rate=1.0,
            governance_participation=1.0,
        )

        weight = engine.calculate_weight(contributor)
        assert weight == 1.0

    def test_zero_weight(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Test",
            historical_contribution=0.0,
            current_period_attribution=0.0,
            success_rate=0.0,
            governance_participation=0.0,
        )

        weight = engine.calculate_weight(contributor)
        assert weight == 0.0

    @pytest.mark.parametrize(
        "h,curr,sr,gov,expected",
        [
            (0.0, 0.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0, 0.4),
            (0.0, 1.0, 0.0, 0.0, 0.3),
            (0.0, 0.0, 1.0, 0.0, 0.2),
            (0.0, 0.0, 0.0, 1.0, 0.1),
            (0.5, 0.5, 0.5, 0.5, 0.5),
        ],
    )
    def test_weight_formula_parametrized(self, h, curr, sr, gov, expected):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Test",
            historical_contribution=h,
            current_period_attribution=curr,
            success_rate=sr,
            governance_participation=gov,
        )

        weight = engine.calculate_weight(contributor)
        assert weight == pytest.approx(expected, abs=1e-4)


class TestDistributionEngineComputePayouts:
    def make_contributors(self):
        return [
            Contributor(
                contributor_id="contrib-001",
                name="Alice",
                historical_contribution=0.8,
                current_period_attribution=0.7,
                success_rate=0.9,
                governance_participation=0.5,
            ),
            Contributor(
                contributor_id="contrib-002",
                name="Bob",
                historical_contribution=0.6,
                current_period_attribution=0.5,
                success_rate=0.8,
                governance_participation=0.3,
            ),
        ]

    def test_empty_contributors(self):
        engine = DistributionEngine()
        payouts = engine.compute_payouts([], total_pool=100.0)
        assert payouts == []

    def test_zero_total_pool(self):
        engine = DistributionEngine()
        contributors = self.make_contributors()
        payouts = engine.compute_payouts(contributors, total_pool=0.0)

        for payout in payouts:
            assert payout.amount == 0.0

    def test_single_contributor(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Alice",
            historical_contribution=0.5,
            current_period_attribution=0.5,
            success_rate=0.5,
            governance_participation=0.5,
        )
        payouts = engine.compute_payouts([contributor], total_pool=100.0)

        assert len(payouts) == 1
        assert payouts[0].amount == pytest.approx(100.0, abs=1e-4)

    def test_two_contributors_split_proportionally(self):
        engine = DistributionEngine()
        contributors = self.make_contributors()
        total_pool = 100.0

        payouts = engine.compute_payouts(contributors, total_pool)

        total_payout = sum(p.amount for p in payouts)
        assert total_payout == pytest.approx(total_pool, abs=1e-3)

    def test_payouts_sorted_by_amount_descending(self):
        engine = DistributionEngine()
        contributors = self.make_contributors()
        payouts = engine.compute_payouts(contributors, total_pool=100.0)

        for i in range(len(payouts) - 1):
            assert payouts[i].amount >= payouts[i + 1].amount

    def test_roles_in_payout(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Alice",
            historical_contribution=0.5,
            current_period_attribution=0.5,
            success_rate=0.5,
            governance_participation=0.5,
        )
        payouts = engine.compute_payouts([contributor], total_pool=100.0)

        assert payouts[0].roles is not None
        for role in CONTRIBUTOR_SECONDARY_SPLIT:
            assert role in payouts[0].roles

    def test_roles_sum_to_payout_amount(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Alice",
            historical_contribution=0.5,
            current_period_attribution=0.5,
            success_rate=0.5,
            governance_participation=0.5,
        )
        payouts = engine.compute_payouts([contributor], total_pool=100.0)

        role_total = sum(payouts[0].roles.values())
        assert role_total == pytest.approx(payouts[0].amount, abs=1e-4)


class TestDistributionEngineSettle:
    def test_settle_with_no_revenue_returns_none(self):
        engine = DistributionEngine()
        report = engine.settle(SettlementPeriod.DAILY)
        assert report is None

    def test_settle_with_revenue(self):
        engine = DistributionEngine()
        call = SkillCall(
            skill_id="skill-001",
            caller_id="caller-001",
            input_data={"key": "value"},
            revenue_usd=1.0,
        )
        engine.distribute(call)

        report = engine.settle(SettlementPeriod.DAILY)

        assert report is not None
        assert report.total_revenue == pytest.approx(1.0, abs=1e-6)
        assert report.platform_total == pytest.approx(0.05, abs=1e-6)
        assert report.ecosystem_total == pytest.approx(0.25, abs=1e-6)
        assert report.contributor_total == pytest.approx(0.70, abs=1e-6)

    def test_settle_with_multiple_distributions(self):
        engine = DistributionEngine()
        for i in range(5):
            call = SkillCall(
                skill_id="skill-001",
                caller_id="caller-001",
                input_data={"key": "value"},
                revenue_usd=2.0,
                call_id=f"call-{i}",
            )
            engine.distribute(call)

        report = engine.settle(SettlementPeriod.DAILY)
        assert report is not None
        assert report.total_revenue == pytest.approx(10.0, abs=1e-6)

    def test_settle_period_field(self):
        engine = DistributionEngine()
        call = SkillCall(
            skill_id="skill-001",
            caller_id="caller-001",
            input_data={"key": "value"},
            revenue_usd=1.0,
        )
        engine.distribute(call)

        report = engine.settle(SettlementPeriod.DAILY)
        assert report is not None
        assert report.period == SettlementPeriod.DAILY

    def test_settle_total_distributions(self):
        engine = DistributionEngine()
        for i in range(3):
            call = SkillCall(
                skill_id="skill-001",
                caller_id="caller-001",
                input_data={"key": "value"},
                revenue_usd=1.0,
                call_id=f"call-{i}",
            )
            engine.distribute(call)

        report = engine.settle(SettlementPeriod.DAILY)
        assert report is not None
        assert report.total_distributions == 3


class TestDistributionEngineRegisterContributor:
    def test_register_and_retrieve(self):
        engine = DistributionEngine()
        contributor = Contributor(
            contributor_id="contrib-001",
            name="Alice",
        )
        engine.register_contributor(contributor)

        retrieved = engine.get_contributor("contrib-001")
        assert retrieved is not None
        assert retrieved.name == "Alice"

    def test_get_nonexistent_contributor(self):
        engine = DistributionEngine()
        assert engine.get_contributor("nonexistent") is None

    def test_register_overwrites_existing(self):
        engine = DistributionEngine()
        c1 = Contributor(contributor_id="contrib-001", name="Alice")
        c2 = Contributor(contributor_id="contrib-001", name="Bob")

        engine.register_contributor(c1)
        engine.register_contributor(c2)

        retrieved = engine.get_contributor("contrib-001")
        assert retrieved is not None
        assert retrieved.name == "Bob"

    def test_settle_uses_registered_contributors(self):
        engine = DistributionEngine()
        engine.register_contributor(Contributor(contributor_id="contrib-001", name="Alice"))
        engine.register_contributor(Contributor(contributor_id="contrib-002", name="Bob"))

        call = SkillCall(
            skill_id="skill-001",
            caller_id="caller-001",
            input_data={"key": "value"},
            revenue_usd=1.0,
        )
        engine.distribute(call)

        report = engine.settle(SettlementPeriod.DAILY)
        assert report is not None
        assert len(report.payouts) == 2


class TestDistributionEnginePeriodHelpers:
    def test_daily_period_key_format(self):
        key = DistributionEngine._get_current_period_key(SettlementPeriod.DAILY)
        now = datetime.datetime.now(datetime.UTC)
        expected = now.strftime("%Y-%m-%d")
        assert key == expected

    def test_weekly_period_key_format(self):
        key = DistributionEngine._get_current_period_key(SettlementPeriod.WEEKLY)
        now = datetime.datetime.now(datetime.UTC)
        iso = now.isocalendar()
        expected = f"{iso.year}-W{iso.week:02d}"
        assert key == expected

    def test_monthly_period_key_format(self):
        key = DistributionEngine._get_current_period_key(SettlementPeriod.MONTHLY)
        now = datetime.datetime.now(datetime.UTC)
        expected = now.strftime("%Y-%m")
        assert key == expected

    def test_period_start_daily(self):
        ts = DistributionEngine._get_period_start(SettlementPeriod.DAILY)
        now = datetime.datetime.now(datetime.UTC)
        expected = now.replace(hour=0, minute=0, second=0, microsecond=0)
        assert ts == expected.timestamp()

    def test_period_start_monthly(self):
        ts = DistributionEngine._get_period_start(SettlementPeriod.MONTHLY)
        now = datetime.datetime.now(datetime.UTC)
        expected = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        assert ts == expected.timestamp()

    def test_settle_report_fields_consistency(self):
        engine = DistributionEngine()
        call = SkillCall(
            skill_id="skill-001",
            caller_id="caller-001",
            input_data={"key": "value"},
            revenue_usd=1.0,
        )
        engine.distribute(call)

        report = engine.settle(SettlementPeriod.DAILY)
        assert report is not None
        assert report.period_start > 0
        assert report.period_end > 0
        assert report.period_end >= report.period_start
