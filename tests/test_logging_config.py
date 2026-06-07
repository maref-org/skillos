"""Tests for skillos.kernel.logging_config — Structured Logging"""

import json
import logging

import pytest

from skillos.kernel.logging_config import (
    TraceContext,
    extra_var,
    generate_trace_id,
    get_logger,
    setup_logging,
    trace_id_var,
)


@pytest.fixture(autouse=True)
def _reset_context_vars():
    token_trace = trace_id_var.set("")
    token_extra = extra_var.set({})
    yield
    trace_id_var.reset(token_trace)
    extra_var.reset(token_extra)


class TestSetupLogging:
    def test_setup_logging_replaces_handlers(self):
        setup_logging(logging.DEBUG)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) >= 1

    def test_get_logger_returns_logger(self):
        logger = get_logger(__name__)
        assert isinstance(logger, logging.Logger)


class TestTraceContext:
    def test_TraceContext_sets_var(self):
        with TraceContext(trace_id="test-123") as tid:
            assert tid == "test-123"
            assert trace_id_var.get() == "test-123"
        assert trace_id_var.get() == ""

    def test_TraceContext_auto_generates_id(self):
        with TraceContext() as tid:
            assert len(tid) == 16
            assert trace_id_var.get() == tid

    def test_TraceContext_resets_after_exit(self):
        trace_id_var.set("original")
        with TraceContext(trace_id="nested"):
            assert trace_id_var.get() == "nested"
        assert trace_id_var.get() == "original"

    def test_TraceContext_with_extra(self):
        with TraceContext(trace_id="abc", user="alice", source="test"):
            logger = get_logger(__name__)
            logger.info("test message")

    def test_nested_contexts(self):
        with TraceContext(trace_id="outer") as outer:
            with TraceContext(trace_id="inner") as inner:
                assert trace_id_var.get() == "inner"
                assert outer != inner
            assert trace_id_var.get() == "outer"


class TestGenerateTraceId:
    def test_generates_hex_string(self):
        tid = generate_trace_id()
        assert isinstance(tid, str)
        assert len(tid) == 16
        int(tid, 16)

    def test_unique_ids(self):
        ids = {generate_trace_id() for _ in range(100)}
        assert len(ids) == 100


class TestStructuredOutput:
    def test_logger_outputs_json(self, capsys):
        setup_logging(logging.INFO)
        logger = get_logger("test.module")
        with TraceContext(trace_id="json-test", request_id="123"):
            logger.warning("test warning message")
        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]
        assert len(lines) > 0
        log_entry = json.loads(lines[0])
        assert log_entry["trace_id"] == "json-test"
        assert log_entry["level"] == "WARNING"
        assert log_entry["msg"] == "test warning message"
        assert log_entry["logger"] == "test.module"
        assert log_entry["extra"] == {"request_id": "123"}

    def test_TraceContext_exception_resets(self):
        trace_id_var.set("original")
        try:
            with TraceContext(trace_id="will-fail"):
                assert trace_id_var.get() == "will-fail"
                raise ValueError("test error")
        except ValueError:
            pass
        assert trace_id_var.get() == "original"

    def test_logger_output_trace_id_empty(self, capsys):
        setup_logging(logging.INFO)
        logger = get_logger("test.module")
        logger.info("no trace id")
        captured = capsys.readouterr()
        lines = [l for l in captured.err.split("\n") if l.strip()]
        assert len(lines) > 0
        log_entry = json.loads(lines[0])
        assert log_entry["trace_id"] == ""
