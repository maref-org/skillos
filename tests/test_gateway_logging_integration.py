"""Integration tests: ProtocolGateway × LoggingConfig trace_id propagation"""

import json
import logging

from skillos.kernel.logging_config import TraceContext, get_logger, setup_logging
from skillos.protocol.protocol_gateway import ProtocolGateway, ProtocolType


class TestGatewayLoggingIntegration:
    def test_gateway_route_logs_consistent_trace_id(self, capsys):
        setup_logging(logging.INFO)
        gateway = ProtocolGateway()
        get_logger("test.integration")

        resp = gateway.route("agent-001", ProtocolType.A2A, {"action": "test"})

        captured = capsys.readouterr()
        lines = [json.loads(l) for l in captured.err.split("\n") if l.strip()]

        assert len(lines) > 0
        for entry in lines:
            assert entry["trace_id"] == resp.trace_id

    def test_gateway_generates_new_trace_id(self, capsys):
        setup_logging(logging.INFO)
        gateway = ProtocolGateway()

        resp = gateway.route("agent-001", ProtocolType.A2A, {"action": "test"})

        assert resp.trace_id != ""
        assert len(resp.trace_id) == 16

    def test_gateway_trace_id_unique_per_request(self, capsys):
        setup_logging(logging.INFO)
        gateway = ProtocolGateway()

        resp1 = gateway.route("a1", ProtocolType.A2A, {})
        resp2 = gateway.route("a2", ProtocolType.A2A, {})

        assert resp1.trace_id != resp2.trace_id

    def test_gateway_isolation_from_outer_context(self, capsys):
        setup_logging(logging.INFO)
        gateway = ProtocolGateway()

        with TraceContext(trace_id="outer-context", user="alice"):
            resp = gateway.route("agent-001", ProtocolType.A2A, {})

        assert resp.trace_id != "outer-context"

        captured = capsys.readouterr()
        lines = [json.loads(l) for l in captured.err.split("\n") if l.strip()]

        gateway_logs = [e for e in lines if e.get("extra", {}).get("target") == "agent-001"]
        assert all(e["trace_id"] == resp.trace_id for e in gateway_logs)
