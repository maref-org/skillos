"""Tests for kernel.slo — SLO/SLI definition and error budget"""

import time

from skillos.kernel.slo import (
    ErrorBudget,
    SLIMeasurement,
    SLOConfig,
    SLOManager,
    SLOStatus,
)


class TestSLOConfig:
    def test_default_config(self):
        config = SLOConfig(name="test", target_percentile_latency_ms=500.0, target_availability_pct=99.5)
        assert config.name == "test"
        assert config.target_percentile_latency_ms == 500.0
        assert config.target_availability_pct == 99.5
        assert config.window_hours == 720

    def test_sli_definitions(self):
        config = SLOConfig(name="test", target_percentile_latency_ms=500.0, target_availability_pct=99.5)
        assert config.sli_latency.name == "p99_latency"
        assert config.sli_latency.measurement_unit == "ms"
        assert config.sli_availability.name == "availability"


class TestSLIManager:
    def test_default_configs_exist(self):
        manager = SLOManager()
        assert set(manager._configs.keys()) == {"skill_call", "protocol_gateway", "negmarket_api", "kernel_routing"}

    def test_record_latency_within_slo(self):
        manager = SLOManager()
        m = manager.record_latency("skill_call", 300.0)
        assert m.passed is True

    def test_record_latency_exceeds_slo(self):
        manager = SLOManager()
        m = manager.record_latency("skill_call", 600.0)
        assert m.passed is False

    def test_record_availability_success(self):
        manager = SLOManager()
        m = manager.record_availability("skill_call", True)
        assert m.passed is True

    def test_record_availability_failure(self):
        manager = SLOManager()
        m = manager.record_availability("skill_call", False)
        assert m.passed is False

    def test_error_budget_healthy_without_data(self):
        manager = SLOManager()
        budget = manager.compute_error_budget("skill_call")
        assert budget is not None
        assert budget.status == SLOStatus.HEALTHY
        assert budget.remaining_pct == 100.0

    def test_error_budget_exhausted(self):
        manager = SLOManager()
        # 720h window with 99.5% target = 12960s budget; need >12960 failures
        for _ in range(13000):
            manager.record_availability("skill_call", False)
        budget = manager.compute_error_budget("skill_call")
        assert budget is not None
        assert budget.status is SLOStatus.EXHAUSTED

    def test_error_budget_unknown_slo(self):
        manager = SLOManager()
        assert manager.compute_error_budget("nonexistent") is None

    def test_get_slo_summary_structure(self):
        manager = SLOManager()
        manager.record_latency("skill_call", 100.0)
        summary = manager.get_slo_summary()
        assert "skill_call" in summary
        assert summary["skill_call"]["target_latency_ms"] == 500.0
        assert "error_budget" in summary["skill_call"]

    def test_get_slo_manager_singleton(self):
        from skillos.kernel.slo import get_slo_manager

        m1 = get_slo_manager()
        m2 = get_slo_manager()
        assert m1 is m2


class TestErrorBudget:
    def test_healthy_status_high_remaining(self):
        budget = ErrorBudget(
            total_budget_seconds=1000.0,
            consumed_seconds=10.0,
            remaining_seconds=990.0,
            remaining_pct=99.0,
            burn_rate=0.01,
            status=SLOStatus.HEALTHY,
            window_hours=720,
        )
        assert budget.remaining_pct == 99.0
        assert budget.status == SLOStatus.HEALTHY


class TestSLIMeasurement:
    def test_timestamp_set(self):
        before = time.time()
        m = SLIMeasurement(timestamp=time.time(), value=100.0, passed=True)
        after = time.time()
        assert before <= m.timestamp <= after
