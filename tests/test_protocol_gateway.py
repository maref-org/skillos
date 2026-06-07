"""Tests for skillos.protocol.protocol_gateway — Protocol Gateway"""

import pytest

from skillos.protocol.protocol_gateway import (
    ProtocolGateway,
    ProtocolType,
)


@pytest.fixture
def gateway():
    return ProtocolGateway()


class TestProtocolType:
    def test_all_values_present(self):
        values = {m.value for m in ProtocolType}
        assert "a2a" in values
        assert "mcp" in values
        assert "acp" in values
        assert "anp" in values
        assert "awcp" in values


class TestProtocolGateway:
    def test_a2a_route(self, gateway):
        resp = gateway.route(
            "agent-001",
            ProtocolType.A2A,
            {"action": "analyze", "query": "market trends"},
        )
        assert resp.success is True
        assert resp.result["protocol"] == "a2a"
        assert resp.result["target_id"] == "agent-001"
        assert resp.result["action"] == "analyze"
        assert resp.trace_id != ""
        assert resp.latency_ms >= 0

    def test_mcp_route_fails_without_server(self, gateway):
        resp = gateway.route(
            "skill-weather",
            ProtocolType.MCP,
            {"action": "execute", "input": "Shanghai"},
        )
        assert resp.success is True
        assert resp.result["protocol"] == "mcp"
        assert resp.result["target_id"] == "skill-weather"
        assert resp.result["status"] == "failed"

    def test_unsupported_protocol(self, gateway):
        resp = gateway.route(
            "test",
            ProtocolType.ACP,
            {"action": "run"},
        )
        assert resp.success is False
        assert "Unsupported protocol" in resp.error
        assert resp.trace_id != ""

    def test_another_unsupported(self, gateway):
        resp = gateway.route(
            "test",
            ProtocolType.ANP,
            {},
        )
        assert resp.success is False

    def test_awcp_unsupported(self, gateway):
        resp = gateway.route(
            "test",
            ProtocolType.AWCP,
            {},
        )
        assert resp.success is False

    def test_route_with_empty_payload(self, gateway):
        resp = gateway.route("agent-001", ProtocolType.A2A, {})
        assert resp.success is True
        assert resp.result["action"] == "execute"

    def test_multiple_routes(self, gateway):
        for _ in range(10):
            resp = gateway.route(
                "agent-001",
                ProtocolType.A2A,
                {"action": "ping"},
            )
            assert resp.success is True

    def test_trace_id_unique_per_request(self, gateway):
        resp1 = gateway.route("a1", ProtocolType.A2A, {})
        resp2 = gateway.route("a2", ProtocolType.A2A, {})
        assert resp1.trace_id != resp2.trace_id

    def test_route_none_target(self, gateway):
        resp = gateway.route(None, ProtocolType.A2A, {})
        assert resp.success is False
        assert resp.error != ""

    def test_route_non_dict_payload(self, gateway):
        resp = gateway.route("agent-001", ProtocolType.A2A, "invalid")
        assert resp.success is False
        assert resp.error != ""

    def test_supported_protocols(self, gateway):
        assert ProtocolType.A2A in gateway.SUPPORTED_PROTOCOLS
        assert ProtocolType.MCP in gateway.SUPPORTED_PROTOCOLS
        assert ProtocolType.ACP not in gateway.SUPPORTED_PROTOCOLS
