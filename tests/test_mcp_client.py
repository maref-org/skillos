"""Tests for protocol.mcp_client — MCP protocol connector"""

import pytest

from skillos.protocol.mcp_client import MCPCallResult, MCPClient, MCPError, MCPTool


class TestMCPClientBuildRequest:
    def test_build_request_structure(self):
        payload = MCPClient._build_request("tools/list", {})
        assert payload["jsonrpc"] == "2.0"
        assert "id" in payload
        assert payload["method"] == "tools/list"
        assert payload["params"] == {}

    def test_build_request_with_params(self):
        payload = MCPClient._build_request("tools/call", {"name": "test"})
        assert payload["method"] == "tools/call"
        assert payload["params"] == {"name": "test"}

    def test_build_request_unique_id(self):
        ids = {MCPClient._build_request("ping", {})["id"] for _ in range(100)}
        assert len(ids) == 100


class TestMCPTool:
    def test_defaults(self):
        tool = MCPTool(name="search")
        assert tool.name == "search"
        assert tool.description == ""
        assert tool.input_schema == {}

    def test_full_init(self):
        tool = MCPTool(
            name="analyze",
            description="Analyze a document",
            input_schema={"type": "object", "properties": {}},
        )
        assert tool.name == "analyze"
        assert tool.description == "Analyze a document"
        assert tool.input_schema["type"] == "object"


class TestMCPCallResult:
    def test_defaults(self):
        result = MCPCallResult(success=True, content=[])
        assert result.success is True
        assert result.content == []
        assert result.is_error is False
        assert result.latency_ms == 0.0

    def test_error_result(self):
        result = MCPCallResult(success=False, content=[], is_error=True)
        assert result.success is False
        assert result.is_error is True


class TestMCPClientEdgeCases:
    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        client = MCPClient()
        await client.close()
        await client.close()

    def test_protocol_error_message(self):
        err = MCPError("Server unavailable")
        assert str(err) == "Server unavailable"
        assert isinstance(err, Exception)
