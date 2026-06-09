#!/usr/bin/env python3
"""MCP Client — 真实 MCP 协议连接器

实现 MCP (Model Context Protocol) 客户端规范，支持：
  - JSON-RPC 2.0 over HTTP/SSE
  - 工具列表获取 (tools/list)
  - 工具调用 (tools/call)
  - 连接池 + 超时 + 重试
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from skillos.kernel.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.0


class MCPError(Exception):
    """MCP 协议错误"""


@dataclass
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPCallResult:
    success: bool
    content: list[dict[str, Any]]
    is_error: bool = False
    latency_ms: float = 0.0


class MCPClient:
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    async def close(self):
        await self._client.aclose()

    async def list_tools(self, server_url: str) -> list[MCPTool]:
        payload = self._build_request("tools/list", {})
        result = await self._post(server_url, payload)
        tools_data = result.get("tools", [])
        return [
            MCPTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]

    async def call_tool(
        self,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPCallResult:
        start = time.monotonic()
        payload = self._build_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments or {},
            },
        )
        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                result = await self._post(server_url, payload)
                elapsed = (time.monotonic() - start) * 1000
                is_error = result.get("isError", False)
                return MCPCallResult(
                    success=not is_error,
                    content=result.get("content", []),
                    is_error=is_error,
                    latency_ms=round(elapsed, 2),
                )
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_BACKOFF * (2**attempt)
                    logger.warning(
                        "MCP call attempt %d failed, retrying in %.1fs: %s",
                        attempt + 1,
                        wait,
                        e,
                    )
                    time.sleep(wait)
        raise MCPError(f"MCP call failed after {_MAX_RETRIES} retries: {last_error}")

    async def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise MCPError(f"MCP server error: {data['error']}")
        return data.get("result", {})

    @staticmethod
    def _build_request(method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
