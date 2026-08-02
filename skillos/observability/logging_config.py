#!/usr/bin/env python3
"""Structured Logging — structlog 结构化日志配置

职责：
  - 统一日志格式为结构化 JSON
  - 自动注入 trace_id、user_id、skill_id
  - 支持多环境配置（dev / prod）

使用方式：
    from skillos.observability.logging_config import get_logger
    logger = get_logger("skillos.kernel")
    logger.info("skill_executed", skill_id="s1", latency_ms=120)

环境变量：
    SKILLOS_LOG_LEVEL — 日志级别（默认 INFO）
    SKILLOS_LOG_FORMAT — json 或 console（默认 json）
"""

import logging
import os
import sys
from typing import Any


class _StructuredLogAdapter(logging.LoggerAdapter):
    """标准 logging 的适配器，支持结构化字段注入"""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        extra = kwargs.get("extra", {})
        # 合并结构化字段
        structured = {k: v for k, v in kwargs.items() if k not in ("exc_info", "stack_info", "extra")}
        if structured:
            extra["structured"] = structured
            kwargs["extra"] = extra
            # 清理已提取的字段
            for k in structured:
                kwargs.pop(k, None)
        return msg, kwargs

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        msg, kwargs = self.process(msg, kwargs)
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        msg, kwargs = self.process(msg, kwargs)
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        msg, kwargs = self.process(msg, kwargs)
        self.logger.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        msg, kwargs = self.process(msg, kwargs)
        self.logger.debug(msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        msg, kwargs = self.process(msg, kwargs)
        self.logger.critical(msg, *args, **kwargs)


class JSONFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import time

        log_obj: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.filename}:{record.lineno}",
        }

        # 注入 trace 上下文
        from skillos.observability.tracing import get_current_span_id, get_current_trace_id

        trace_id = get_current_trace_id()
        span_id = get_current_span_id()
        if trace_id:
            log_obj["trace_id"] = trace_id
        if span_id:
            log_obj["span_id"] = span_id

        # 注入结构化字段
        if hasattr(record, "structured"):
            log_obj.update(record.structured)

        # 异常信息
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """控制台友好格式（开发环境）"""

    def format(self, record: logging.LogRecord) -> str:
        base = f"[{record.levelname}] {record.name}: {record.getMessage()}"
        if hasattr(record, "structured"):
            import json

            base += f" | {json.dumps(record.structured, ensure_ascii=False, default=str)}"
        return base


def configure_logging() -> None:
    """配置全局日志系统"""
    level_str = os.getenv("SKILLOS_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    log_format = os.getenv("SKILLOS_LOG_FORMAT", "json").lower()

    # 根日志配置
    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有 handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter()

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # 抑制第三方库噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger("skillos").info("Logging configured: level=%s format=%s", level_str, log_format)


def get_logger(name: str) -> _StructuredLogAdapter:
    """获取结构化日志记录器

    使用方式：
        logger = get_logger("skillos.kernel")
        logger.info("event_name", key1="value1", key2=42)
    """
    return _StructuredLogAdapter(logging.getLogger(name), {})


# 自动配置（首次导入时）
_configure_done = False


def ensure_configured() -> None:
    global _configure_done
    if not _configure_done:
        configure_logging()
        _configure_done = True
