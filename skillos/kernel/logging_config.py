"""Structured logging configuration for SkillOS

Usage:
    from skillos.kernel.logging_config import setup_logging, get_logger, trace_context

    setup_logging(level=logging.INFO)
    logger = get_logger(__name__)

    with TraceContext(trace_id="abc-123", extra={"user": "alice"}):
        logger.info("Hello %s", "world")
"""

import json
import logging
import uuid
from contextvars import ContextVar
from typing import Any

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
extra_var: ContextVar[dict[str, Any]] = ContextVar("extra", default={})


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extra = extra_var.get()
        return json.dumps(
            {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": record.levelname,
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "trace_id": trace_id_var.get(),
                "msg": record.getMessage(),
                "extra": extra or None,
            },
            ensure_ascii=False,
            default=str,
        )


_DEFAULT_FORMAT = "%(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter(_DEFAULT_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class TraceContext:
    """Context manager for trace_id and extra fields.

    Usage:
        with TraceContext(trace_id="abc-123", user="alice"):
            logger.info("processing request")
    """

    def __init__(self, trace_id: str | None = None, **extra: Any):
        self._trace_id = trace_id or uuid.uuid4().hex[:16]
        self._extra = extra
        self._token_trace: Any = None
        self._token_extra: Any = None

    def __enter__(self) -> str:
        self._token_trace = trace_id_var.set(self._trace_id)
        self._token_extra = extra_var.set(self._extra)
        return self._trace_id

    def __exit__(self, *args: Any) -> None:
        trace_id_var.reset(self._token_trace)
        extra_var.reset(self._token_extra)


def generate_trace_id() -> str:
    return uuid.uuid4().hex[:16]
