"""Tests for observability module — metrics, tracing, structured logging"""

import json
import logging
import time
from unittest.mock import patch

import pytest

from skillos.observability.logging_config import (
    ConsoleFormatter,
    JSONFormatter,
    configure_logging,
    ensure_configured,
    get_logger,
)
from skillos.observability.metrics import MetricsCollector, get_metrics
from skillos.observability.tracing import Tracer, get_current_trace_id, get_tracer

# === Metrics Tests ===


class TestMetricsCollector:
    def test_metrics_no_op_without_prometheus(self):
        """未安装 prometheus-client 时应以 no-op 模式运行"""
        with patch.object(MetricsCollector, "_setup"):
            metrics = MetricsCollector()
            metrics._enabled = False
            assert metrics.enabled is False
            metrics.record_request("/test", 200, 0.1)
            metrics.record_error("TestError")
            metrics.record_skill_execution("skill-1", "success", 100.0)
            metrics.record_settlement(10.5)
            metrics.set_session_active_count(5)
            metrics.record_audit_event("skill.executed")

    def test_metrics_text_when_disabled(self):
        metrics = MetricsCollector()
        text = metrics.get_metrics_text()
        assert text.startswith("# HELP") or text.startswith("# TYPE")

    def test_timed_decorator_no_exception(self):
        metrics = MetricsCollector()

        @metrics.timed("/test_endpoint")
        def success_func():
            return "ok"

        result = success_func()
        assert result == "ok"

    def test_timed_decorator_with_exception(self):
        metrics = MetricsCollector()

        @metrics.timed("/test_endpoint")
        def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            fail_func()

    def test_get_metrics_singleton(self):
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2


class TestMetricsSnapshotEndpoint:
    def test_snapshot_returns_zeros_when_disabled(self):
        """M1 修复：prometheus 未启用时 /monitoring/metrics 应返回 0 而非 500。"""
        from skillos.observability.metrics import MetricsCollector

        with patch.object(MetricsCollector, "_setup"):
            metrics = MetricsCollector()
            metrics._enabled = False
            with patch("skillos.web_api.monitoring.get_metrics", return_value=metrics):
                # 异步端点需跑事件循环
                import asyncio

                from skillos.web_api.monitoring import metrics_snapshot

                result = asyncio.run(metrics_snapshot())
                assert result == {"requests_total": 0, "errors_total": 0, "active_sessions": 0}

    def test_snapshot_reads_real_values_when_enabled(self):
        """M1 修复：prometheus 启用时返回真实计数器（_value.get() 版本安全）。"""
        from skillos.observability.metrics import MetricsCollector

        metrics = MetricsCollector()
        metrics.record_request("/test", 200, 0.01)
        with patch("skillos.web_api.monitoring.get_metrics", return_value=metrics):
            import asyncio

            from skillos.web_api.monitoring import metrics_snapshot

            result = asyncio.run(metrics_snapshot())
            assert result["requests_total"] == 1
            assert result["errors_total"] == 0


# === Tracing Tests ===


class TestTracer:
    def test_tracer_enabled_with_opentelemetry(self):
        tracer = Tracer()
        assert tracer.enabled is True

    def test_span_lifecycle(self):
        tracer = Tracer()
        with tracer.span("test_operation", {"key": "value"}) as span:
            assert span.name == "test_operation"
            assert span.attributes["key"] == "value"
            assert span.trace_id is not None
            assert span.span_id is not None
            assert span.start_time is not None
            span.set_attribute("status", "running")
            span.add_event("checkpoint", {"step": 1})

        assert span.end_time is not None
        assert span.attributes["status"] == "running"
        assert len(span.events) == 1
        assert "duration_ms" in span.attributes

    def test_span_exception_handling(self):
        tracer = Tracer()
        with pytest.raises(RuntimeError, match="test error"):
            with tracer.span("failing_op"):
                raise RuntimeError("test error")

        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].status == "error"
        assert "test error" in spans[0].attributes.get("status_description", "")

    def test_trace_decorator(self):
        tracer = Tracer()

        @tracer.trace("test_func")
        def my_function():
            return 42

        result = my_function()
        assert result == 42
        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_func"
        assert spans[0].status == "ok"

    def test_trace_decorator_exception(self):
        tracer = Tracer()

        @tracer.trace("failing_func")
        def my_function():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            my_function()

        spans = tracer.get_spans()
        assert spans[0].status == "error"

    def test_extract_trace_context(self):
        tracer = Tracer()
        ctx = tracer.extract_trace_context({"X-Trace-ID": "abc123", "X-Span-ID": "span456"})
        assert ctx == {"trace_id": "abc123", "span_id": "span456"}

        ctx_none = tracer.extract_trace_context({})
        assert ctx_none is None

    def test_inject_trace_context(self):
        tracer = Tracer()
        headers = tracer.inject_trace_context()
        # 无当前 trace 时，不应注入
        assert "X-Trace-ID" not in headers

    def test_get_tracer_singleton(self):
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2

    def test_trace_context_propagation(self):
        tracer = Tracer()
        with tracer.span("parent") as parent:
            # 验证上下文已设置
            assert get_current_trace_id() == parent.trace_id
            with tracer.span("child") as child:
                assert child.trace_id == parent.trace_id
                assert child.parent_id == parent.span_id


# === Logging Tests ===


class TestStructuredLogging:
    def test_json_formatter(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "test message"
        assert "timestamp" in parsed
        assert "source" in parsed

    def test_json_formatter_with_structured(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.structured = {"skill_id": "s1", "latency_ms": 120}
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["skill_id"] == "s1"
        assert parsed["latency_ms"] == 120

    def test_console_formatter(self):
        formatter = ConsoleFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "[INFO]" in output
        assert "test message" in output

    def test_structured_log_adapter(self):
        logger = get_logger("test.adapter")
        # 验证适配器能正常调用
        logger.info("event_name", skill_id="s1", latency_ms=120)

    def test_configure_logging(self):
        with patch.dict("os.environ", {"SKILLOS_LOG_LEVEL": "DEBUG", "SKILLOS_LOG_FORMAT": "console"}):
            configure_logging()
            root = logging.getLogger()
            assert root.level == logging.DEBUG

    def test_ensure_configured_idempotent(self):
        ensure_configured()
        # 多次调用不应报错
        ensure_configured()


# === Integration Tests ===


class TestObservabilityIntegration:
    def test_metrics_tracing_logging_together(self):
        """验证三个组件可以协同工作"""
        metrics = MetricsCollector()
        tracer = Tracer()

        with tracer.span("api_request", {"endpoint": "/api/test"}) as span:
            start = time.monotonic()
            # 模拟业务逻辑
            time.sleep(0.001)
            duration = time.monotonic() - start

            metrics.record_request("/api/test", 200, duration)
            span.set_attribute("status", "success")
            span.set_attribute("duration_ms", round(duration * 1000, 2))

        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].attributes["status"] == "success"

    def test_trace_id_in_log_output(self):
        """验证 trace_id 可以注入到日志输出中"""
        tracer = Tracer()
        formatter = JSONFormatter()

        with tracer.span("test_op") as span:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="with trace",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed.get("trace_id") == span.trace_id
