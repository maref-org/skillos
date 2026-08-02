#!/usr/bin/env python3
"""Metrics — Prometheus 指标采集

职责：
  - RED 指标：Rate、Errors、Duration
  - 业务指标：Skill 执行、结算、会话
  - 暴露 /metrics 端点（通过 start_http_server）

使用方式：
    from skillos.observability.metrics import MetricsCollector
    metrics = MetricsCollector()
    metrics.record_request("/api/v1/skills", 200, 0.045)
    metrics.record_skill_execution("skill-001", "success", 120.0)
"""

import logging
import os
import time
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])


class MetricsCollector:
    """Prometheus 指标采集器

    自动检测 prometheus-client 是否安装，未安装时以 no-op 模式运行。
    """

    def __init__(self, prefix: str = "skillos") -> None:
        self._prefix = prefix
        self._enabled = False
        self._registry: Any = None

        # RED 指标
        self._requests_total: Any = None
        self._errors_total: Any = None
        self._request_duration: Any = None

        # 业务指标
        self._skill_executions_total: Any = None
        self._settlement_amount_usd: Any = None
        self._session_active_count: Any = None
        self._audit_events_total: Any = None

        self._setup()

    def _setup(self) -> None:
        try:
            from prometheus_client import (
                CollectorRegistry,
                Counter,
                Gauge,
                Histogram,
                start_http_server,
            )

            self._registry = CollectorRegistry()

            self._requests_total = Counter(
                f"{self._prefix}_requests_total",
                "Total requests by endpoint and status",
                ["endpoint", "status_code"],
                registry=self._registry,
            )

            self._errors_total = Counter(
                f"{self._prefix}_errors_total",
                "Total errors by type",
                ["error_type"],
                registry=self._registry,
            )

            self._request_duration = Histogram(
                f"{self._prefix}_request_duration_seconds",
                "Request duration in seconds",
                ["endpoint"],
                buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
                registry=self._registry,
            )

            self._skill_executions_total = Counter(
                f"{self._prefix}_skill_executions_total",
                "Total skill executions by skill_id and status",
                ["skill_id", "status"],
                registry=self._registry,
            )

            self._settlement_amount_usd = Counter(
                f"{self._prefix}_settlement_amount_usd",
                "Total settlement amount in USD",
                ["period"],
                registry=self._registry,
            )

            self._session_active_count = Gauge(
                f"{self._prefix}_session_active_count",
                "Number of active sessions",
                registry=self._registry,
            )

            self._audit_events_total = Counter(
                f"{self._prefix}_audit_events_total",
                "Total audit events by type",
                ["event_type"],
                registry=self._registry,
            )

            self._enabled = True
            logger.info("Prometheus metrics initialized with prefix: %s", self._prefix)

            # 如果配置了端口，启动 HTTP server
            port_str = os.getenv("SKILLOS_METRICS_PORT")
            if port_str:
                port = int(port_str)
                start_http_server(port, registry=self._registry)
                logger.info("Prometheus metrics server started on port %d", port)

        except ImportError:
            logger.warning(
                "prometheus-client not installed. Metrics will be collected in-memory only. "
                "Install with: pip install prometheus-client"
            )
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def registry(self) -> Any:
        return self._registry

    def record_request(self, endpoint: str, status_code: int, duration_seconds: float) -> None:
        """记录 HTTP/API 请求指标"""
        if not self._enabled:
            return
        self._requests_total.labels(endpoint=endpoint, status_code=str(status_code)).inc()
        self._request_duration.labels(endpoint=endpoint).observe(duration_seconds)

    def record_error(self, error_type: str) -> None:
        """记录错误指标"""
        if not self._enabled:
            return
        self._errors_total.labels(error_type=error_type).inc()

    def record_skill_execution(self, skill_id: str, status: str, latency_ms: float) -> None:
        """记录 Skill 执行指标"""
        if not self._enabled:
            return
        self._skill_executions_total.labels(skill_id=skill_id, status=status).inc()
        # 同时记录到 duration histogram（统一用秒）
        self._request_duration.labels(endpoint=f"/skill/{skill_id}").observe(latency_ms / 1000.0)

    def record_settlement(self, amount_usd: float, period: str = "daily") -> None:
        """记录结算金额指标"""
        if not self._enabled:
            return
        self._settlement_amount_usd.labels(period=period).inc(amount_usd)

    def set_session_active_count(self, count: int) -> None:
        """设置活跃会话数"""
        if not self._enabled:
            return
        self._session_active_count.set(count)

    def record_audit_event(self, event_type: str) -> None:
        """记录审计事件指标"""
        if not self._enabled:
            return
        self._audit_events_total.labels(event_type=event_type).inc()

    def timed(self, endpoint: str) -> Callable[[_F], _F]:
        """装饰器：自动记录函数执行时间和请求计数

        使用方式：
            @metrics.timed("/api/v1/skills")
            def handle_request():
                ...
        """

        def decorator(func: _F) -> _F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.monotonic()
                try:
                    result = func(*args, **kwargs)
                    status = 200
                    return result
                except Exception as exc:
                    status = 500
                    self.record_error(type(exc).__name__)
                    raise
                finally:
                    duration = time.monotonic() - start
                    self.record_request(endpoint, status, duration)

            return wrapper  # type: ignore[return-value]

        return decorator

    def get_metrics_text(self) -> str:
        """获取 Prometheus 格式的指标文本（用于非 HTTP server 场景）"""
        if not self._enabled or self._registry is None:
            return "# metrics disabled\n"
        try:
            from prometheus_client import generate_latest

            return generate_latest(self._registry).decode("utf-8")
        except ImportError:
            return "# prometheus-client not installed\n"


# 全局单例（惰性初始化）
_metrics_instance: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """获取全局 MetricsCollector 实例"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance


def reset_metrics() -> None:
    """重置单例（仅供测试使用）。"""
    global _metrics_instance
    _metrics_instance = None
