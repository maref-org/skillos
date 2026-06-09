"""Protocol Gateway — 五协议轻量路由网关

将外部协议 (A2A, MCP, ACP, ANP, AWCP) 统一路由到 SkillOS 内部调用。
当前支持 A2A 和 MCP 协议路由，其余为预留扩展。

Usage:
    gateway = ProtocolGateway()
    result = gateway.route("skill-001", ProtocolType.A2A, {"task": "analyze"})
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from skillos.kernel.logging_config import TraceContext, generate_trace_id, get_logger
from skillos.protocol.mcp_client import MCPClient, MCPError

logger = get_logger(__name__)


class ProtocolType(StrEnum):
    A2A = "a2a"
    MCP = "mcp"
    ACP = "acp"
    ANP = "anp"
    AWCP = "awcp"


@dataclass
class GatewayRequest:
    protocol: ProtocolType
    target_id: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=generate_trace_id)
    timestamp: float = field(default_factory=time.time)


@dataclass
class GatewayResponse:
    success: bool
    result: Any = None
    error: str | None = None
    trace_id: str = ""
    latency_ms: float = 0.0


class ProtocolGateway:
    SUPPORTED_PROTOCOLS: set[ProtocolType] = {ProtocolType.A2A, ProtocolType.MCP}

    def route(self, target_id: str, protocol: ProtocolType, payload: dict[str, Any]) -> GatewayResponse:
        start = time.monotonic()
        if not target_id:
            return GatewayResponse(success=False, error="target_id is required")
        if not isinstance(payload, dict):
            return GatewayResponse(success=False, error="payload must be a dict")
        req = GatewayRequest(
            protocol=protocol,
            target_id=target_id,
            action=payload.get("action", "execute"),
            payload=payload,
        )

        with TraceContext(trace_id=req.trace_id, protocol=protocol.value, target=target_id):
            if protocol not in self.SUPPORTED_PROTOCOLS:
                elapsed = (time.monotonic() - start) * 1000
                return GatewayResponse(
                    success=False,
                    error=f"Unsupported protocol: {protocol.value}",
                    trace_id=req.trace_id,
                    latency_ms=round(elapsed, 2),
                )

            try:
                handler = self._get_handler(protocol)
                result = handler(target_id, req)
                elapsed = (time.monotonic() - start) * 1000
                return GatewayResponse(
                    success=True,
                    result=result,
                    trace_id=req.trace_id,
                    latency_ms=round(elapsed, 2),
                )
            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                logger.error("Protocol route failed: %s -> %s: %s", protocol.value, target_id, e)
                return GatewayResponse(
                    success=False,
                    error=str(e),
                    trace_id=req.trace_id,
                    latency_ms=round(elapsed, 2),
                )

    def _get_handler(self, protocol: ProtocolType):
        handlers = {
            ProtocolType.A2A: self._handle_a2a,
            ProtocolType.MCP: self._handle_mcp,
        }
        return handlers[protocol]

    def _handle_a2a(self, target_id: str, req: GatewayRequest) -> dict[str, Any]:
        logger.info(
            "A2A route: %s action=%s",
            target_id,
            req.action,
        )
        return {
            "protocol": "a2a",
            "target_id": target_id,
            "action": req.action,
            "status": "dispatched",
            "trace_id": req.trace_id,
        }

    def _handle_mcp(self, target_id: str, req: GatewayRequest) -> dict[str, Any]:
        logger.info("MCP route: %s action=%s", target_id, req.action)
        try:
            import asyncio

            client = MCPClient()
            tool_name = req.payload.get("tool", "execute")
            result = asyncio.run(
                client.call_tool(
                    f"http://localhost:8000/mcp/v1/{target_id}",
                    tool_name,
                    req.payload.get("args"),
                )
            )
            return {
                "protocol": "mcp",
                "target_id": target_id,
                "action": req.action,
                "status": "completed",
                "result": result.content,
                "trace_id": req.trace_id,
            }
        except MCPError as e:
            logger.error("MCP call failed: %s", e)
            return {
                "protocol": "mcp",
                "target_id": target_id,
                "action": req.action,
                "status": "failed",
                "error": str(e),
                "trace_id": req.trace_id,
            }
        except Exception as e:
            logger.error("MCP route unexpected error: %s", e)
            return {
                "protocol": "mcp",
                "target_id": target_id,
                "action": req.action,
                "status": "failed",
                "error": str(e),
                "trace_id": req.trace_id,
            }
