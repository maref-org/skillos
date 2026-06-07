#!/usr/bin/env python3
"""SLO/SLI — 服务水平目标与指标定义

定义 4 个核心 SLO:
  1. Skill 调用可用性: P99 latency < 500ms, availability > 99.5%
  2. 协议网关可用性: P99 latency < 200ms, availability > 99.9%
  3. NegMarket API 可用性: P99 latency < 1000ms, availability > 99.0%
  4. 内核路由可用性: P99 latency < 100ms, availability > 99.9%

每个 SLO 包含:
  - SLI 定义 (如何测量)
  - 目标值 (SLO)
  - 燃烧率计算
  - 错误预算窗口
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SLOStatus(StrEnum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    BURNING = "burning"
    EXHAUSTED = "exhausted"


@dataclass
class SLIDefinition:
    name: str
    description: str
    measurement_unit: str


@dataclass
class SLOConfig:
    name: str
    target_percentile_latency_ms: float
    target_availability_pct: float
    window_hours: int = 720  # 30 days

    sli_latency: SLIDefinition = field(default_factory=lambda: SLIDefinition(
        name="p99_latency", description="P99 响应延迟", measurement_unit="ms",
    ))
    sli_availability: SLIDefinition = field(default_factory=lambda: SLIDefinition(
        name="availability", description="请求成功率", measurement_unit="%",
    ))


@dataclass
class SLIMeasurement:
    timestamp: float
    value: float
    passed: bool


@dataclass
class ErrorBudget:
    total_budget_seconds: float
    consumed_seconds: float
    remaining_seconds: float
    remaining_pct: float
    burn_rate: float
    status: SLOStatus
    window_hours: int


class SLOManager:
    _DEFAULT_CONFIGS: dict[str, SLOConfig] = {
        "skill_call": SLOConfig(
            name="skill_call",
            target_percentile_latency_ms=500.0,
            target_availability_pct=99.5,
        ),
        "protocol_gateway": SLOConfig(
            name="protocol_gateway",
            target_percentile_latency_ms=200.0,
            target_availability_pct=99.9,
        ),
        "negmarket_api": SLOConfig(
            name="negmarket_api",
            target_percentile_latency_ms=1000.0,
            target_availability_pct=99.0,
        ),
        "kernel_routing": SLOConfig(
            name="kernel_routing",
            target_percentile_latency_ms=100.0,
            target_availability_pct=99.9,
        ),
    }

    def __init__(self, configs: dict[str, SLOConfig] | None = None):
        self._configs = configs or dict(self._DEFAULT_CONFIGS)
        self._measurements: dict[str, list[SLIMeasurement]] = {k: [] for k in self._configs}

    def record_latency(self, slo_name: str, latency_ms: float) -> SLIMeasurement:
        config = self._configs[slo_name]
        passed = latency_ms <= config.target_percentile_latency_ms
        m = SLIMeasurement(timestamp=time.time(), value=latency_ms, passed=passed)
        self._measurements[slo_name].append(m)
        return m

    def record_availability(self, slo_name: str, success: bool) -> SLIMeasurement:
        m = SLIMeasurement(timestamp=time.time(), value=1.0 if success else 0.0, passed=success)
        self._measurements[slo_name].append(m)
        return m

    def compute_error_budget(self, slo_name: str) -> ErrorBudget | None:
        config = self._configs.get(slo_name)
        if not config:
            return None
        measurements = self._measurements.get(slo_name, [])
        window_sec = config.window_hours * 3600
        now = time.time()
        windowed = [m for m in measurements if now - m.timestamp <= window_sec]
        total_requests = len(windowed)
        if total_requests == 0:
            total_budget = window_sec * (1 - config.target_availability_pct / 100)
            return ErrorBudget(
                total_budget_seconds=round(total_budget, 2),
                consumed_seconds=0.0,
                remaining_seconds=round(total_budget, 2),
                remaining_pct=100.0,
                burn_rate=0.0,
                status=SLOStatus.HEALTHY,
                window_hours=config.window_hours,
            )
        failures = sum(1 for m in windowed if not m.passed)
        total_budget = window_sec * (1 - config.target_availability_pct / 100)
        consumed = failures * 1.0
        remaining = max(0.0, total_budget - consumed)
        remaining_pct = (remaining / total_budget * 100) if total_budget > 0 else 0.0
        if remaining_pct == 0:
            status = SLOStatus.EXHAUSTED
        elif remaining_pct < 25:
            status = SLOStatus.BURNING
        elif remaining_pct < 50:
            status = SLOStatus.AT_RISK
        else:
            status = SLOStatus.HEALTHY
        return ErrorBudget(
            total_budget_seconds=round(total_budget, 2),
            consumed_seconds=round(consumed, 2),
            remaining_seconds=round(remaining, 2),
            remaining_pct=round(remaining_pct, 2),
            burn_rate=round(consumed / max(total_budget, 1), 4),
            status=status,
            window_hours=config.window_hours,
        )

    def get_slo_summary(self) -> dict[str, Any]:
        summary = {}
        for name in self._configs:
            config = self._configs[name]
            budget = self.compute_error_budget(name)
            summary[name] = {
                "target_latency_ms": config.target_percentile_latency_ms,
                "target_availability": config.target_availability_pct,
                "error_budget": {
                    "status": budget.status.value if budget else "unknown",
                    "remaining_pct": budget.remaining_pct if budget else 0.0,
                },
            }
        return summary


_SLO_MANAGER: SLOManager | None = None


def get_slo_manager() -> SLOManager:
    global _SLO_MANAGER
    if _SLO_MANAGER is None:
        _SLO_MANAGER = SLOManager()
    return _SLO_MANAGER
