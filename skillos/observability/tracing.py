#!/usr/bin/env python3
"""Tracing — OpenTelemetry 分布式追踪

职责：
  - 生成/传播 trace_id
  - 自动包裹关键函数调用
  - 与 HTTP Header X-Trace-ID 对接

使用方式：
    from skillos.observability.tracing import Tracer
    tracer = Tracer()

    with tracer.span("skill_execution", {"skill_id": "s1"}) as span:
        result = execute_skill()
        span.set_attribute("status", "success")

    # 装饰器方式
    @tracer.trace("endpoint")
    def handle_request():
        ...
"""

import logging
import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# 当前 trace context（线程/协程安全）
_current_trace: ContextVar[dict[str, Any] | None] = ContextVar("current_trace", default=None)


class Span:
    """追踪 Span（兼容 OpenTelemetry 风格）"""

    def __init__(self, name: str, trace_id: str, span_id: str, parent_id: str | None = None):
        self.name = name
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.attributes: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.status = "unset"

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        import time
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def set_status(self, status: str, description: str = "") -> None:
        self.status = status
        if description:
            self.attributes["status_description"] = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "attributes": self.attributes,
            "events": self.events,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
        }


class Tracer:
    """分布式追踪器

    自动检测 opentelemetry 是否安装，未安装时以内存模式运行。
    """

    def __init__(self, service_name: str = "skillos") -> None:
        self._service_name = service_name
        self._enabled = False
        self._otel_tracer: Any = None
        self._spans: list[Span] = []

        self._setup()

    def _setup(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            resource = Resource.create({SERVICE_NAME: self._service_name})
            provider = TracerProvider(resource=resource)

            # OTLP exporter（如果配置了 endpoint）
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            if otlp_endpoint:
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info("OTLP trace exporter configured: %s", otlp_endpoint)

            trace.set_tracer_provider(provider)
            self._otel_tracer = trace.get_tracer(self._service_name)
            self._enabled = True
            logger.info("OpenTelemetry tracing initialized for service: %s", self._service_name)

        except ImportError:
            logger.warning(
                "opentelemetry not installed. Tracing will be in-memory only. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_current_trace_id(self) -> str | None:
        """获取当前上下文中的 trace_id"""
        ctx = _current_trace.get()
        if ctx:
            return ctx.get("trace_id")
        return None

    def get_current_span_id(self) -> str | None:
        """获取当前上下文中的 span_id"""
        ctx = _current_trace.get()
        if ctx:
            return ctx.get("span_id")
        return None

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
    ) -> Generator[Span, None, None]:
        """创建并管理一个 Span 的生命周期"""
        import time

        trace_id = self.get_current_trace_id() or self._generate_trace_id()
        span_id = self._generate_span_id()
        current_span_id = self.get_current_span_id()

        # 自动设置 parent_id：如果当前已有 span，则以其为父；否则使用传入的 parent_span_id
        effective_parent_id = parent_span_id if parent_span_id is not None else current_span_id

        span = Span(name=name, trace_id=trace_id, span_id=span_id, parent_id=effective_parent_id)
        span.start_time = time.time()
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)

        # 设置上下文
        token = _current_trace.set({"trace_id": trace_id, "span_id": span_id})

        try:
            if self._enabled and self._otel_tracer:
                with self._otel_tracer.start_as_current_span(name) as otel_span:
                    if attributes:
                        for k, v in attributes.items():
                            otel_span.set_attribute(k, v)
                    yield span
            else:
                yield span
        except Exception as exc:
            span.set_status("error", str(exc))
            raise
        finally:
            span.end_time = time.time()
            span.set_attribute("duration_ms", round((span.end_time - span.start_time) * 1000, 2))
            self._spans.append(span)
            _current_trace.reset(token)

    def trace(self, name: str, attributes: dict[str, Any] | None = None) -> Callable[[_F], _F]:
        """装饰器：自动包裹函数调用为 Span"""
        def decorator(func: _F) -> _F:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.span(name, attributes) as span:
                    span.set_attribute("function", func.__qualname__)
                    try:
                        result = func(*args, **kwargs)
                        span.set_status("ok")
                        return result
                    except Exception as exc:
                        span.set_status("error", str(exc))
                        raise
            return wrapper  # type: ignore[return-value]
        return decorator

    def extract_trace_context(self, headers: dict[str, str]) -> dict[str, str] | None:
        """从 HTTP Headers 中提取追踪上下文"""
        trace_id = headers.get("X-Trace-ID") or headers.get("x-trace-id")
        span_id = headers.get("X-Span-ID") or headers.get("x-span-id")
        if trace_id:
            return {"trace_id": trace_id, "span_id": span_id or ""}
        return None

    def inject_trace_context(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """向 HTTP Headers 中注入追踪上下文"""
        if headers is None:
            headers = {}
        trace_id = self.get_current_trace_id()
        span_id = self.get_current_span_id()
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        if span_id:
            headers["X-Span-ID"] = span_id
        return headers

    def get_spans(self) -> list[Span]:
        """获取所有记录的 spans（内存模式下调试使用）"""
        return list(self._spans)

    def clear_spans(self) -> None:
        """清除内存中的 spans"""
        self._spans.clear()

    @staticmethod
    def _generate_trace_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _generate_span_id() -> str:
        return uuid.uuid4().hex[:16]


# 全局单例
tracers: dict[str, Tracer] = {}


def get_tracer(service_name: str = "skillos") -> Tracer:
    """获取全局 Tracer 实例"""
    if service_name not in tracers:
        tracers[service_name] = Tracer(service_name)
    return tracers[service_name]


def get_current_trace_id() -> str | None:
    """获取当前上下文中的 trace_id（便捷函数）"""
    ctx = _current_trace.get()
    if ctx:
        return ctx.get("trace_id")
    return None


def get_current_span_id() -> str | None:
    """获取当前上下文中的 span_id（便捷函数）"""
    ctx = _current_trace.get()
    if ctx:
        return ctx.get("span_id")
    return None
