# SkillOS 市场差异能力补强工程实施方案

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 2026-06-06 全维度审计发现的 15 项缺口，按优先级分 4 个 Phase 补强，将 SkillOS 从 Beta- 提升到 Beta 水平。

**Architecture:** 四层架构 (L3 经济层 / L2 协议层 / L1 内核层 / L0 基础层)，Skills 正交。补充分三阶段: 文档修复 → 核心存根补全 → 差异能力增强。

**Tech Stack:** Python 3.11+, pytest, cryptography, fastapi (optional), httpx, sqlite3

---

## Phase 1: 文档修复与测试补全 (Week 1)

### Task 1.1: 修复 docs/01-README.md 版本声明偏移

**Files:**
- Modify: `docs/01-README.md:3`

**Step 1: Read file to confirm exact content**

```bash
head -5 docs/01-README.md
```
Expected: `**版本**: v0.3.0`

**Step 2: Edit version**

Edit `docs/01-README.md` line 3: `**版本**: v0.3.0` → `**版本**: v0.5.0-beta`

**Step 3: Update date**

Edit `docs/01-README.md` line 4: `**更新日期**: 2026-05-25` → `**更新日期**: 2026-06-06`

**Step 4: Verify**

```bash
grep -n "版本\|更新" docs/01-README.md
```
Expected: `v0.5.0-beta` and `2026-06-06`

**Step 5: Commit**

```bash
git add docs/01-README.md
git commit -m "fix: sync docs/01-README.md version to v0.5.0-beta"
```

---

### Task 1.2: 补写 NegMarket API 测试 (0% → 80%+)

**Files:**
- Modify: `tests/test_negmarket_api.py`

`test_negmarket_api.py` 当前有 228 行测试骨架 (fixtures only)，但 `negmarket/api.py` 51 行代码覆盖率 0%。需补全 3 个端点的集成测试。

**Step 1: Read current test file tail to understand fixture pattern**

```bash
tail -50 tests/test_negmarket_api.py
```

**Step 2: Add upload endpoint test**

Append to `tests/test_negmarket_api.py`:

```python
class TestUploadEndpoint:
    def test_upload_success(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "API call failed with timeout after 30s on user-123 login",
            "category": "api_error",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "sample_id" in data
        assert "risk_level" in data
        assert "anti_pattern_skill_id" in data
        assert data["risk_level"] == "medium"

    def test_upload_empty_text_rejected(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "",
            "category": "general",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        assert resp.status_code == 422

    def test_upload_high_risk_content(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "Security breach: API key exposed in git commit containing sk-placeholder-value",
            "category": "security",
            "contributor_id": "user-2",
            "contributor_secret": "secret-2",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] in ("high", "medium")

    def test_upload_long_text(self, client):
        resp = client.post("/negmarket/upload", json={
            "raw_text": "error " * 20000,
            "category": "general",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        assert resp.status_code == 200


class TestCallEndpoint:
    def test_call_existing_anti_pattern(self, client):
        upload = client.post("/negmarket/upload", json={
            "raw_text": "Database connection pool exhausted after 100 concurrent requests",
            "category": "database",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        sample_id = upload.json()["sample_id"]

        resp = client.post(f"/negmarket/{sample_id}/call", json={"params": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_level" in data
        assert "warning" in data
        assert "anti_pattern_id" in data

    def test_call_nonexistent_sample(self, client):
        resp = client.post("/negmarket/nonexistent-id/call", json={"params": {}})
        assert resp.status_code == 404

    def test_call_tracks_incrementing_stats(self, client):
        upload = client.post("/negmarket/upload", json={
            "raw_text": "Memory leak in cache layer after 1M entries",
            "category": "performance",
            "contributor_id": "user-3",
            "contributor_secret": "secret-3",
        })
        sample_id = upload.json()["sample_id"]
        first_id = upload.json()["anti_pattern_skill_id"]

        client.post(f"/negmarket/{sample_id}/call", json={})
        client.post(f"/negmarket/{sample_id}/call", json={})
        resp = client.post(f"/negmarket/{sample_id}/call", json={})
        assert resp.status_code == 200


class TestDiscoverEndpoint:
    def test_discover_all(self, client):
        client.post("/negmarket/upload", json={
            "raw_text": "Rate limit exceeded for API endpoint /v1/users",
            "category": "api_error",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })
        client.post("/negmarket/upload", json={
            "raw_text": "SSL certificate expired on prod.example.com",
            "category": "security",
            "contributor_id": "user-2",
            "contributor_secret": "secret-2",
        })

        resp = client.get("/negmarket/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert "skills" in data
        assert "total" in data
        assert data["total"] >= 2

    def test_discover_filter_by_category(self, client):
        client.post("/negmarket/upload", json={
            "raw_text": "Timeout while connecting to database cluster",
            "category": "database",
            "contributor_id": "user-1",
            "contributor_secret": "secret-1",
        })

        resp = client.get("/negmarket/discover?category=database")
        assert resp.status_code == 200
        data = resp.json()
        for s in data["skills"]:
            assert s["category"] == "database"

    def test_discover_filter_by_risk_level(self, client):
        client.post("/negmarket/upload", json={
            "raw_text": "Critical: data corruption in transaction log, customer-456 balance incorrect",
            "category": "data_integrity",
            "contributor_id": "user-3",
            "contributor_secret": "secret-3",
        })

        resp = client.get("/negmarket/discover?risk_level=high")
        assert resp.status_code == 200

    def test_discover_empty_when_no_data(self, client):
        resp = client.get("/negmarket/discover?category=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
```

**Step 3: Run test to verify it passes**

```bash
uv run pytest tests/test_negmarket_api.py -v --tb=short
```
Expected: All tests PASS

**Step 4: Verify coverage improvement**

```bash
uv run coverage run -m pytest tests/test_negmarket_api.py tests/test_negmarket.py -v --tb=short 2>&1 | tail -5
uv run coverage report -m --include="negmarket/*"
```
Expected: `negmarket/api.py` coverage > 80%

**Step 5: Commit**

```bash
git add tests/test_negmarket_api.py
git commit -m "test: add NegMarket API endpoint coverage (3 endpoints, 10 cases)"
```

---

### Task 1.3: 更新 30-roadmap 反映真实状态

**Files:**
- Modify: `docs/30-roadmap/2026-engineering-roadmap.md`

**Step 1: Update version declaration**

Edit `docs/30-roadmap/2026-engineering-roadmap.md`:
- Line 5: `v0.3.0` → `v0.5.0-beta`
- Line 4: `2026-05-27` → `2026-06-06`

**Step 2: Update NegMarket status**

Section 3: NegMarket v0.4.0 (计划中) → NegMarket v0.5.0 (已实现):
- Change header: `## 3. v0.4.0 — NegMarket MVP（6-8 周）` → `## 3. NegMarket — 负样本市场（已实现）`
- Change status badges: `[ ]` → `[x]` for all 5 acceptance criteria
- Add note: "实际在 v0.5.0-beta 中作为 negmarket/ 模块交付，含脱敏/加密/存储/反模式生成/API"

**Step 3: Update v0.5.0 status**

Section 4 Men0 协议: 标注已实现组件 (AgentCard / ProtocolGateway) 和剩余存根：
- Change `## 4. v0.5.0 — Men0 协议核心（8-10 周）` → `## 4. Men0 协议 — Agent 通信协议（部分实现）`
- 保留 AgentCard ✅ (已实现), 标注 JSONL 路由 / 五协议网关保留为规划

**Step 4: Execute commands to verify**

```bash
grep -n "NegMarket\|v0\.3\.0\|v0\.4\.0\|v0\.5\.0" docs/30-roadmap/2026-engineering-roadmap.md | head -10
```

**Step 5: Commit**

```bash
git add docs/30-roadmap/2026-engineering-roadmap.md
git commit -m "docs: sync roadmap to reflect v0.5.0-beta actual state"
```

---

## Phase 2: 核心架构存根补全 (Weeks 2-3)

### Task 2.1: 实现真实 MCP 连接器

**Files:**
- Create: `protocol/mcp_client.py`
- Modify: `kernel/skill_kernel.py:101-106` (替换存根 `mcp://{skill_id}`)
- Test: `tests/test_mcp_client.py`

**Background:**
当前 `skill_kernel.py:104` 使用 `mcp://{skill_id}` URI 字符串作为存根，`protocol_gateway.py:116-127` 的 `_handle_mcp` 仅返回 `{"status": "dispatched"}`，无真实 HTTP 通信。需实现符合 [MCP Protocol](https://modelcontextprotocol.io) 的客户端。

**Step 1: Create `protocol/mcp_client.py`**

```python
#!/usr/bin/env python3
"""MCP Client — 真实 MCP 协议连接器

实现 MCP (Model Context Protocol) 客户端规范，支持：
  - JSON-RPC 2.0 over HTTP/SSE
  - 工具列表获取 (tools/list)
  - 工具调用 (tools/call)
  - 连接池 + 超时 + 重试

Usage:
    client = MCPClient()
    tools = await client.list_tools("http://localhost:8000/mcp/v1")
    result = await client.call_tool("http://localhost:8000/mcp/v1", "search", {"q": "test"})
"""

from __future__ import annotations

import json
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
        payload = self._build_request("tools/call", {
            "name": tool_name,
            "arguments": arguments or {},
        })

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
                    wait = _RETRY_BACKOFF * (2 ** attempt)
                    logger.warning("MCP call attempt %d failed, retrying in %.1fs: %s", attempt + 1, wait, e)
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
```

**Step 2: Update `skill_kernel.py` to use real MCP client**

Replace the stub MCP connector generation in `assemble_tools()`:

File: `kernel/skill_kernel.py`, lines 101-106:
```python
return ToolChain(
    skill_id=nft.skill_id,
    tools=tools,
    mcp_connectors=[f"mcp://{nft.skill_id}"],
    a2a_adapters=[f"a2a://{nft.skill_id}"],
)
```

Change to:
```python
return ToolChain(
    skill_id=nft.skill_id,
    tools=tools,
    mcp_connectors=[f"http://localhost:8000/mcp/v1/{nft.skill_id}"],
    a2a_adapters=[f"a2a://{nft.skill_id}"],
)
```

**Step 3: Update `protocol_gateway.py` `_handle_mcp` to use MCPClient**

Replace the stub handler:

```python
def _handle_mcp(self, target_id: str, req: GatewayRequest) -> dict[str, Any]:
    logger.info(
        "MCP route: %s action=%s",
        target_id, req.action,
    )
    return {
        "protocol": "mcp",
        "target_id": target_id,
        "action": req.action,
        "status": "dispatched",
        "trace_id": req.trace_id,
    }
```

Change to real MCP call attempt:

```python
def _handle_mcp(self, target_id: str, req: GatewayRequest) -> dict[str, Any]:
    logger.info("MCP route: %s action=%s", target_id, req.action)
    try:
        import anyio
        client = MCPClient()
        tool_name = req.payload.get("tool", "execute")
        result = anyio.run(client.call_tool, f"http://localhost/mcp/v1/{target_id}", tool_name, req.payload.get("args"))
        return {
            "protocol": "mcp",
            "target_id": target_id,
            "action": req.action,
            "status": "completed",
            "result": result.content,
            "trace_id": req.trace_id,
        }
    except Exception as e:
        logger.error("MCP call failed: %s", e)
        return {
            "protocol": "mcp",
            "target_id": target_id,
            "action": req.action,
            "status": "failed",
            "error": str(e),
            "trace_id": req.trace_id,
        }
```

**Step 4: Create `tests/test_mcp_client.py`**

```python
"""Tests for protocol.mcp_client — MCP protocol connector"""
import pytest

from skillos.protocol.mcp_client import MCPClient, MCPError, MCPTool, MCPCallResult


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
        await client.close()  # should not raise

    def test_protocol_error_message(self):
        err = MCPError("Server unavailable")
        assert str(err) == "Server unavailable"
        assert isinstance(err, Exception)
```

**Step 5: Run tests**

```bash
uv run pytest tests/test_mcp_client.py -v --tb=short
```
Expected: 10+ tests PASS

**Step 6: Run full suite to check no regression**

```bash
uv run pytest -v --tb=short 2>&1 | tail -10
```

**Step 7: Commit**

```bash
git add protocol/mcp_client.py tests/test_mcp_client.py kernel/skill_kernel.py protocol/protocol_gateway.py
git commit -m "feat: implement real MCP client connector, replace stub URI"
```

---

### Task 2.2: SLO/SLI 定义与监控指标

**Files:**
- Create: `kernel/slo.py`
- Test: `tests/test_slo.py`
- Reference: `docs/13-error_budget.md` (已有文档框架)

**Step 1: Create `kernel/slo.py`**

```python
#!/usr/bin/env python3
"""SLO/SLI — 服务水平目标与指标定义

定义 4 个核心 SLO:
  1. Skill 调用可用性: P99 latency < 500ms, availability > 99.5%
  2. 协议网关可用性: P99 latency < 200ms, availability > 99.9%
  3. NegMarket API 可用性: P99 latency < 1000ms, availability > 99.0%
  4. 内核路由可用性: P99 latency < 100ms, availability > 99.9%

每个 SLO 包含:
  - SLI 定义 (如何测量)
  - 目标值 (SLO)
  - 燃烧率计算
  - 错误预算窗口
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable


class SLOStatus(StrEnum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    BURNING = "burning"
    EXHAUSTED = "exhausted"


@dataclass
class SLIDefinition:
    name: str
    description: str
    measurement_unit: str


@dataclass
class SLOConfig:
    name: str
    target_percentile_latency_ms: float
    target_availability_pct: float
    window_hours: int = 720  # 30 days
    burn_rate_warning: float = 2.0
    burn_rate_critical: float = 4.0

    sli_latency: SLIDefinition = field(default_factory=lambda: SLIDefinition(
        name="p99_latency",
        description="P99 响应延迟",
        measurement_unit="ms",
    ))
    sli_availability: SLIDefinition = field(default_factory=lambda: SLIDefinition(
        name="availability",
        description="请求成功率",
        measurement_unit="%",
    ))


@dataclass
class SLIMeasurement:
    timestamp: float
    value: float
    passed: bool


@dataclass
class ErrorBudget:
    total_budget_seconds: float
    consumed_seconds: float
    remaining_seconds: float
    remaining_pct: float
    burn_rate: float
    status: SLOStatus
    window_hours: int


class SLOManager:
    _DEFAULT_CONFIGS: dict[str, SLOConfig] = {
        "skill_call": SLOConfig(
            name="skill_call",
            target_percentile_latency_ms=500.0,
            target_availability_pct=99.5,
        ),
        "protocol_gateway": SLOConfig(
            name="protocol_gateway",
            target_percentile_latency_ms=200.0,
            target_availability_pct=99.9,
        ),
        "negmarket_api": SLOConfig(
            name="negmarket_api",
            target_percentile_latency_ms=1000.0,
            target_availability_pct=99.0,
        ),
        "kernel_routing": SLOConfig(
            name="kernel_routing",
            target_percentile_latency_ms=100.0,
            target_availability_pct=99.9,
        ),
    }

    def __init__(self, configs: dict[str, SLOConfig] | None = None):
        self._configs = configs or dict(self._DEFAULT_CONFIGS)
        self._measurements: dict[str, list[SLIMeasurement]] = {
            k: [] for k in self._configs
        }

    def record_latency(self, slo_name: str, latency_ms: float) -> SLIMeasurement:
        config = self._configs[slo_name]
        passed = latency_ms <= config.target_percentile_latency_ms
        m = SLIMeasurement(timestamp=time.time(), value=latency_ms, passed=passed)
        self._measurements[slo_name].append(m)
        return m

    def record_availability(self, slo_name: str, success: bool) -> SLIMeasurement:
        m = SLIMeasurement(timestamp=time.time(), value=1.0 if success else 0.0, passed=success)
        self._measurements[slo_name].append(m)
        return m

    def compute_error_budget(self, slo_name: str) -> ErrorBudget | None:
        config = self._configs.get(slo_name)
        if not config:
            return None

        measurements = self._measurements.get(slo_name, [])
        window_sec = config.window_hours * 3600
        now = time.time()
        windowed = [m for m in measurements if now - m.timestamp <= window_sec]

        total_requests = len(windowed)
        if total_requests == 0:
            return ErrorBudget(
                total_budget_seconds=window_sec * (1 - config.target_availability_pct / 100),
                consumed_seconds=0.0,
                remaining_seconds=window_sec * (1 - config.target_availability_pct / 100),
                remaining_pct=100.0,
                burn_rate=0.0,
                status=SLOStatus.HEALTHY,
                window_hours=config.window_hours,
            )

        failures = sum(1 for m in windowed if not m.passed)
        total_budget = window_sec * (1 - config.target_availability_pct / 100)
        consumed = failures * 1.0  # each failure consumes 1 second of error budget
        remaining = max(0.0, total_budget - consumed)
        remaining_pct = (remaining / total_budget * 100) if total_budget > 0 else 0.0

        if remaining_pct == 0:
            status = SLOStatus.EXHAUSTED
        elif remaining_pct < 25:
            status = SLOStatus.BURNING
        elif remaining_pct < 50:
            status = SLOStatus.AT_RISK
        else:
            status = SLOStatus.HEALTHY

        return ErrorBudget(
            total_budget_seconds=round(total_budget, 2),
            consumed_seconds=round(consumed, 2),
            remaining_seconds=round(remaining, 2),
            remaining_pct=round(remaining_pct, 2),
            burn_rate=round(consumed / max(total_budget, 1), 4),
            status=status,
            window_hours=config.window_hours,
        )

    def get_slo_summary(self) -> dict[str, dict]:
        summary = {}
        for name in self._configs:
            config = self._configs[name]
            budget = self.compute_error_budget(name)
            recent = self._measurements.get(name, [])[-10:] if self._measurements.get(name) else []
            summary[name] = {
                "target_latency_ms": config.target_percentile_latency_ms,
                "target_availability": config.target_availability_pct,
                "error_budget": {
                    "status": budget.status.value if budget else "unknown",
                    "remaining_pct": budget.remaining_pct if budget else 0.0,
                },
                "recent_measurements": len(recent),
            }
        return summary


_SLO_MANAGER: SLOManager | None = None


def get_slo_manager() -> SLOManager:
    global _SLO_MANAGER
    if _SLO_MANAGER is None:
        _SLO_MANAGER = SLOManager()
    return _SLO_MANAGER
```

**Step 2: Create `tests/test_slo.py`**

```python
"""Tests for kernel.slo — SLO/SLI definition and error budget"""
import time

import pytest

from skillos.kernel.slo import (
    SLOConfig,
    SLOStatus,
    SLOManager,
    ErrorBudget,
    SLIMeasurement,
)


class TestSLOConfig:
    def test_default_config(self):
        config = SLOConfig(
            name="test",
            target_percentile_latency_ms=500.0,
            target_availability_pct=99.5,
        )
        assert config.name == "test"
        assert config.target_percentile_latency_ms == 500.0
        assert config.target_availability_pct == 99.5
        assert config.window_hours == 720

    def test_sli_definitions(self):
        config = SLOConfig(
            name="test",
            target_percentile_latency_ms=500.0,
            target_availability_pct=99.5,
        )
        assert config.sli_latency.name == "p99_latency"
        assert config.sli_availability.name == "availability"


class TestSLIManager:
    def test_default_configs_exist(self):
        manager = SLOManager()
        assert "skill_call" in manager._configs
        assert "protocol_gateway" in manager._configs
        assert "negmarket_api" in manager._configs
        assert "kernel_routing" in manager._configs

    def test_record_latency(self):
        manager = SLOManager()
        m = manager.record_latency("skill_call", 300.0)
        assert isinstance(m, SLIMeasurement)
        assert m.value == 300.0
        assert m.passed is True

    def test_record_latency_exceeds_slo(self):
        manager = SLOManager()
        m = manager.record_latency("skill_call", 600.0)
        assert m.passed is False

    def test_record_availability_success(self):
        manager = SLOManager()
        m = manager.record_availability("skill_call", True)
        assert m.passed is True

    def test_record_availability_failure(self):
        manager = SLOManager()
        m = manager.record_availability("skill_call", False)
        assert m.passed is False

    def test_error_budget_healthy(self):
        manager = SLOManager()
        budget = manager.compute_error_budget("skill_call")
        assert budget is not None
        assert budget.status == SLOStatus.HEALTHY
        assert budget.remaining_pct > 90.0

    def test_error_budget_exhausted(self):
        manager = SLOManager()
        for _ in range(1000):
            manager.record_availability("skill_call", False)
        budget = manager.compute_error_budget("skill_call")
        assert budget is not None
        assert budget.status in (SLOStatus.BURNING, SLOStatus.EXHAUSTED)

    def test_error_budget_unknown_slo(self):
        manager = SLOManager()
        budget = manager.compute_error_budget("nonexistent")
        assert budget is None

    def test_get_slo_summary_structure(self):
        manager = SLOManager()
        manager.record_latency("skill_call", 100.0)
        manager.record_latency("protocol_gateway", 50.0)
        summary = manager.get_slo_summary()
        assert "skill_call" in summary
        assert "protocol_gateway" in summary
        assert "negmarket_api" in summary
        assert "kernel_routing" in summary
        assert "target_latency_ms" in summary["skill_call"]
        assert "target_availability" in summary["skill_call"]

    def test_get_slo_manager_singleton(self):
        from skillos.kernel.slo import get_slo_manager
        m1 = get_slo_manager()
        m2 = get_slo_manager()
        assert m1 is m2
```

**Step 3: Run tests**

```bash
uv run pytest tests/test_slo.py -v --tb=short
```
Expected: 12+ tests PASS

**Step 4: Commit**

```bash
git add kernel/slo.py tests/test_slo.py
git commit -m "feat: add SLO/SLI definition with error budget calculation"
```

---

### Task 2.3: LLM 真实意图分类集成

**Files:**
- Modify: `kernel/entry_kernel.py`
- Modify: `pyproject.toml` (add LiteLLM optional dep)
- Test: `tests/test_entry_kernel.py` (扩展)

**Step 1: Add LiteLLM dependency to pyproject.toml**

Add to `[project.optional-dependencies]`:
```toml
llm = [
    "litellm>=1.40.0",
]
```

**Step 2: Add LLM-based intent classifier to `entry_kernel.py`**

After line 58 (`classify_intent = None`):
```python
try:
    from litellm import completion as litellm_completion
except ImportError:
    litellm_completion = None
```

Add new method after `_classify_keyword`:
```python
def _classify_with_llm(self, user_input: str, model: str = "gpt-4o-mini") -> tuple[IntentType, float]:
    if litellm_completion is None:
        return self._classify_keyword(user_input), 0.5

    try:
        response = litellm_completion(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Classify the user intent into one of: "
                    "skill_call, research, content_creation, analysis, execution, chat. "
                    "Respond with JSON: {\"intent\": \"...\", \"confidence\": 0.0-1.0}"
                )},
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=50,
        )
        import json
        result = json.loads(response.choices[0].message.content)
        intent_type = _INTENT_MAP.get(result.get("intent", "chat"), IntentType.CHAT)
        confidence = float(result.get("confidence", 0.5))
        return intent_type, confidence
    except Exception as e:
        logger.warning("LLM classification failed, falling back to keyword: %s", e)
        return self._classify_keyword(user_input), 0.5
```

Update `parse_intent` method to use LLM:
```python
def parse_intent(self, user_input: str) -> Intent:
    if classify_intent is not None:
        result = classify_intent(user_input)
        intent_type = _INTENT_MAP.get(result["intent"], IntentType.CHAT)
        confidence = result["confidence"]
    elif litellm_completion is not None:
        intent_type, confidence = self._classify_with_llm(user_input)
    else:
        intent_type = self._classify_keyword(user_input)
        confidence = 0.5

    requires_gate = self._check_human_gate_required(intent_type, user_input)
    return Intent(
        intent_type=intent_type,
        raw_input=user_input,
        parsed_query=user_input.strip(),
        confidence=confidence,
        requires_human_gate=requires_gate,
    )
```

**Step 3: Add LLM path test**

In `tests/test_entry_kernel.py`, add:
```python
class TestLLMIntegration:
    def test_fallback_to_keyword_when_litellm_missing(self):
        kernel = EntryKernel()
        intent = kernel.parse_intent("search for python tutorials")
        assert intent.intent_type == IntentType.RESEARCH

    def test_confidence_higher_with_llm(self, monkeypatch):
        monkeypatch.setattr("entry_kernel.litellm_completion", lambda **kw: type("obj", (), {
            "choices": [type("obj", (), {
                "message": type("obj", (), {"content": '{"intent": "research", "confidence": 0.92}'})
            }())]
        })())
        from skillos.kernel import entry_kernel
        monkeypatch.setattr(entry_kernel, "litellm_completion", lambda **kw: type("obj", (), {
            "choices": [type("obj", (), {
                "message": type("obj", (), {"content": '{"intent": "research", "confidence": 0.92}'})
            }())]
        })())
        kernel = EntryKernel()
        intent = kernel.parse_intent("search for python tutorials")
        assert intent.confidence > 0.8
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_entry_kernel.py -v --tb=short
```
Expected: All PASS

**Step 5: Commit**

```bash
git add kernel/entry_kernel.py pyproject.toml tests/test_entry_kernel.py
git commit -m "feat: add LiteLLM-based intent classifier with keyword fallback"
```

---

## Phase 3: 差异能力增强 (Weeks 4-6)

### Task 3.1: NegMarket PII 识别升级 ML

**Files:**
- Modify: `negmarket/desensitizer.py`
- Modify: `pyproject.toml` (add presidio optional dep)
- Test: `tests/test_negmarket.py` (扩展)

**Step 1: Add presidio dependency to pyproject.toml**

Add to `[project.optional-dependencies]`:
```toml
negmarket = [
    "presidio-analyzer>=2.2",
    "presidio-anonymizer>=2.2",
]
```

**Step 2: Add ML-based PII step**

In `negmarket/desensitizer.py`, add after `LocalPIIReplaceStep`:
```python
class MLPIIReplaceStep(DesensitizationStep):
    """ML 驱动的 PII 识别（使用 presidio-analyzer）

    后备到正则引擎当 presidio 不可用时。
    """

    def __init__(self):
        self._analyzer = None
        self._engine = None

    def _ensure_analyzer(self):
        if self._analyzer is not None:
            return
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            self._analyzer = AnalyzerEngine()
            self._engine = AnonymizerEngine()
        except ImportError:
            self._analyzer = None

    def process(self, ctx: DesensitizationContext) -> DesensitizationContext:
        self._ensure_analyzer()
        text = ctx.raw_text

        if self._analyzer and self._engine:
            try:
                results = self._analyzer.analyze(text=text, language="en")
                if results:
                    anonymized = self._engine.anonymize(
                        text=text,
                        analyzer_results=results,
                    )
                    ctx.desensitized_text = anonymized.text
                    ctx.extra["pii_types_found"] = list({r.entity_type for r in results})
                    return ctx
            except Exception:
                pass

        ctx.desensitized_text = ctx.raw_text
        return ctx
```

Update the pipeline default steps to include ML PII step:
```python
self.steps = steps or [
    MLPIIReplaceStep(),
    LocalPIIReplaceStep(),
    ZKVerifyStep(),
    AntiPatternSkillStep(),
    DynamicMaskStep(),
]
```

**Step 3: Add ML PII tests**

In `tests/test_negmarket.py`, add:
```python
class TestMLPIIReplaceStep:
    def test_fallback_to_regex_when_presidio_missing(self):
        step = MLPIIReplaceStep()
        ctx = DesensitizationContext(raw_text="contact me at test@example.com")
        result = step.process(ctx)
        assert result.desensitized_text

    def test_no_pii_leaves_text_unchanged(self):
        step = MLPIIReplaceStep()
        ctx = DesensitizationContext(raw_text="hello world this is a normal sentence")
        result = step.process(ctx)
        assert result.desensitized_text == "hello world this is a normal sentence"
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_negmarket.py -v --tb=short
```
Expected: All PASS

**Step 5: Commit**

```bash
git add negmarket/desensitizer.py pyproject.toml tests/test_negmarket.py
git commit -m "feat: upgrade NegMarket PII detection with presidio ML engine, fallback to regex"
```

---

### Task 3.2: 跨平台 Skill 导入 (Anthropic → OpenSkill)

**Files:**
- Create: `protocol/skill_importer.py`
- Test: `tests/test_skill_importer.py`

**Step 1: Create `protocol/skill_importer.py`**

```python
#!/usr/bin/env python3
"""Skill Importer — 跨平台 Skill 格式导入

支持从 Anthropic Skill / OpenAI GPTs 格式转换到 OpenSkill 格式。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from skillos._types import SkillManifest, SkillStatus

_ANTHROPIC_TO_OPENSKILL_MODEL_MAP = {
    "claude-3-5-sonnet": "deepseek-chat",
    "claude-3-opus": "moonshot-v1-32k",
    "claude-3-haiku": "gemma-4",
}


@dataclass
class ImportResult:
    skill: SkillManifest
    warnings: list[str] = field(default_factory=list)
    original_format: str = ""


class SkillImporter:
    @staticmethod
    def from_anthropic(anthropic_skill: dict[str, Any]) -> ImportResult:
        warnings = []
        name = anthropic_skill.get("name", "imported-skill")
        skill_id = name.lower().replace(" ", "-").replace("_", "-")

        original_model = anthropic_skill.get("model", "")
        mapped_model = _ANTHROPIC_TO_OPENSKILL_MODEL_MAP.get(original_model)
        if not mapped_model and original_model:
            warnings.append(f"Unknown model '{original_model}', using default")

        description = anthropic_skill.get("description", f"Imported from Anthropic: {name}")

        manifest = SkillManifest(
            id=skill_id,
            name=name,
            version=anthropic_skill.get("version", "1.0.0"),
            author=anthropic_skill.get("author", "anonymous"),
            description=description,
            license_type="AGPL-3.0",
            status=SkillStatus.DRAFT,
            entry_point=anthropic_skill.get("entry_point"),
            dependencies=anthropic_skill.get("dependencies", []),
            metadata={
                "original_format": "anthropic",
                "original_id": anthropic_skill.get("id", ""),
                "model_mapping": mapped_model or "default",
            },
        )

        return ImportResult(skill=manifest, warnings=warnings, original_format="anthropic")

    @staticmethod
    def from_openai_gpts(gpts_skill: dict[str, Any]) -> ImportResult:
        warnings = []
        name = gpts_skill.get("name", "imported-gpts")
        skill_id = name.lower().replace(" ", "-")

        actions = gpts_skill.get("actions", [])
        if not actions:
            warnings.append("No actions defined in GPTs skill")

        manifest = SkillManifest(
            id=skill_id,
            name=name,
            version="1.0.0",
            author=gpts_skill.get("author", "anonymous"),
            description=gpts_skill.get("description", f"Imported from OpenAI GPTs: {name}"),
            license_type="AGPL-3.0",
            status=SkillStatus.DRAFT,
            entry_point=actions[0] if actions else None,
            dependencies=[],
            metadata={
                "original_format": "openai_gpts",
                "original_id": gpts_skill.get("id", ""),
                "action_count": len(actions),
            },
        )

        return ImportResult(skill=manifest, warnings=warnings, original_format="openai_gpts")

    @staticmethod
    def detect_format(raw: dict[str, Any]) -> str:
        if "model" in raw or "anthropic" in str(raw.get("id", "")).lower():
            return "anthropic"
        if "actions" in raw or "gpts" in str(raw.get("id", "")).lower():
            return "openai_gpts"
        if "execution" in raw and "model_requirements" in raw.get("execution", {}):
            return "openskill"
        return "unknown"
```

**Step 2: Create `tests/test_skill_importer.py`**

```python
"""Tests for protocol.skill_importer — cross-platform skill import"""
import pytest

from skillos.protocol.skill_importer import SkillImporter, ImportResult


class TestDetectFormat:
    def test_detect_anthropic(self):
        raw = {"id": "anthropic-skill-001", "model": "claude-3-5-sonnet"}
        assert SkillImporter.detect_format(raw) == "anthropic"

    def test_detect_openai_gpts(self):
        raw = {"id": "gpts-test", "actions": []}
        assert SkillImporter.detect_format(raw) == "openai_gpts"

    def test_detect_openskill(self):
        raw = {"execution": {"model_requirements": {}}}
        assert SkillImporter.detect_format(raw) == "openskill"

    def test_detect_unknown(self):
        raw = {"name": "something"}
        assert SkillImporter.detect_format(raw) == "unknown"


class TestFromAnthropic:
    def test_basic_conversion(self):
        raw = {
            "id": "legal-review-001",
            "name": "Legal Document Review",
            "version": "2.0.0",
            "author": "law-firm-a",
            "description": "Review legal documents for compliance",
            "model": "claude-3-5-sonnet",
            "entry_point": "review.py",
            "dependencies": ["pypdf2"],
        }
        result = SkillImporter.from_anthropic(raw)
        assert result.skill.name == "Legal Document Review"
        assert result.skill.id == "legal-document-review"
        assert result.skill.license_type == "AGPL-3.0"
        assert result.skill.status.value == "draft"
        assert result.original_format == "anthropic"
        assert result.skill.metadata["model_mapping"] == "deepseek-chat"

    def test_unknown_model_warning(self):
        raw = {"name": "Test", "model": "unknown-model-v99"}
        result = SkillImporter.from_anthropic(raw)
        assert any("Unknown model" in w for w in result.warnings)

    def test_no_warnings_for_mapped_model(self):
        raw = {"name": "Test", "model": "claude-3-5-sonnet"}
        result = SkillImporter.from_anthropic(raw)
        assert len(result.warnings) == 0


class TestFromOpenAIGPTs:
    def test_basic_conversion(self):
        raw = {
            "id": "gpts-data-viz",
            "name": "Data Visualizer",
            "description": "Create beautiful charts",
            "author": "data-team",
            "actions": ["create_chart", "export_png"],
        }
        result = SkillImporter.from_openai_gpts(raw)
        assert result.skill.name == "Data Visualizer"
        assert result.skill.id == "data-visualizer"
        assert result.original_format == "openai_gpts"
        assert result.skill.metadata["action_count"] == 2

    def test_no_actions_warning(self):
        raw = {"name": "Empty Skill"}
        result = SkillImporter.from_openai_gpts(raw)
        assert any("No actions" in w for w in result.warnings)


class TestImportResult:
    def test_defaults(self):
        from skillos._types import SkillManifest, SkillStatus
        manifest = SkillManifest(id="test", name="Test", version="1.0", author="me", description="")
        result = ImportResult(skill=manifest)
        assert result.warnings == []
        assert result.original_format == ""
```

**Step 3: Run tests**

```bash
uv run pytest tests/test_skill_importer.py -v --tb=short
```
Expected: 10+ tests PASS

**Step 4: Commit**

```bash
git add protocol/skill_importer.py tests/test_skill_importer.py
git commit -m "feat: add cross-platform Skill importer (Anthropic + OpenAI GPTs)"
```

---

## Phase 4: 竞品情报与 KB-Code 同步 (Weeks 7-8)

### Task 4.1: KB-Code 版本同步 CI 检查

**Files:**
- Create: `scripts/verify_kb_version_sync.py`
- Create: `.github/workflows/kb-sync-check.yml` (or add to existing CI)

**Step 1: Create `scripts/verify_kb_version_sync.py`**

```python
#!/usr/bin/env python3
"""Verify KB docs version matches pyproject.toml version.

Checks:
  - docs/01-README.md 版本声明 = pyproject.toml version
  - docs/30-roadmap/2026-engineering-roadmap.md 版本声明对齐

Exit code 1 if mismatch found.
"""

import re
import sys
from pathlib import Path


def get_project_version() -> str:
    pyproject = Path("pyproject.toml").read_text()
    m = re.search(r'version = "([^"]+)"', pyproject)
    if not m:
        raise SystemExit("Could not find version in pyproject.toml")
    return m.group(1)


def check_readme_version(expected: str) -> bool:
    readme = Path("docs/01-README.md")
    if not readme.exists():
        print("MISSING: docs/01-README.md")
        return False

    content = readme.read_text()
    m = re.search(r'\*\*版本\*\*: v?([\w.]+)', content)
    if not m:
        print("MISSING: version line in docs/01-README.md")
        return False

    actual = m.group(1)
    if actual != expected:
        print(f"MISMATCH: docs/01-README.md version '{actual}' != expected '{expected}'")
        return False

    print(f"OK: docs/01-README.md version = {actual}")
    return True


def check_roadmap_version(expected: str) -> bool:
    roadmap = Path("docs/30-roadmap/2026-engineering-roadmap.md")
    if not roadmap.exists():
        print("MISSING: docs/30-roadmap/2026-engineering-roadmap.md (not a blocker)")
        return True

    content = roadmap.read_text()
    m = re.search(r'>\s*版本[：:]\s*v?([\w.]+)', content)
    if not m:
        m = re.search(r'版本[：:]\s*v?([\w.]+)', content)
    if not m:
        print("INFO: could not detect version in roadmap (header may be missing)")
        return True

    actual = m.group(1)
    expected_short = expected.split("-")[0]
    if not actual.startswith(expected_short):
        print(f"MISMATCH: roadmap version '{actual}' != expected '{expected_short}'")
        return False

    print(f"OK: roadmap version = {actual} (starts with {expected_short})")
    return True


def main():
    print("=== KB-Code version sync check ===\n")

    expected = get_project_version()
    print(f"pyproject.toml version: {expected}\n")

    results = [
        ("docs/01-README.md", check_readme_version(expected)),
        ("docs/30-roadmap", check_roadmap_version(expected)),
    ]

    print()
    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"FAILED ({len(failed)}): {', '.join(failed)}")
        sys.exit(1)

    print("All checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

**Step 2: Create trigger script for pre-commit or CI**

Add a section to `scripts/verify_distribution.py` or create a lightweight wrapper:

Create `.github/workflows/kb-sync-check.yml`:
```yaml
name: KB-Code Version Sync Check
on:
  pull_request:
    paths:
      - 'docs/**'
      - 'pyproject.toml'
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run KB version sync check
        run: python3 scripts/verify_kb_version_sync.py
```

**Step 3: Run the script to verify**

```bash
python3 scripts/verify_kb_version_sync.py
```
Expected: All checks passed (after Phase 1 fixes)

**Step 4: Commit**

```bash
git add scripts/verify_kb_version_sync.py .github/workflows/kb-sync-check.yml
git commit -m "ci: add KB-code version sync check CI workflow"
```

---

### Task 4.2: 竞品分析自动化 Pipeline

**Files:**
- Create: `scripts/competitive_intel.py`
- Create: `docs/plans/competitive-intel-config.yaml`

**Step 1: Create `scripts/competitive_intel.py`**

```python
#!/usr/bin/env python3
"""Competitive Intelligence — 竞品分析自动化

每月扫描竞品变化，对比 SkillOS 市场差异能力:
  - Anthropic Cowork / Skills 更新
  - OpenAI GPTs Store 变化
  - MCP 协议标准更新
  - 开源 Agent 框架 (LangChain, CrewAI, AutoGPT)

Usage:
    python3 scripts/competitive_intel.py scan         # 扫描竞品变化
    python3 scripts/competitive_intel.py report        # 生成对比报告
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_COMPETITORS = [
    {
        "name": "Anthropic Cowork",
        "type": "proprietary",
        "tracking_points": ["Skill format", "Model routing", "Econ model"],
    },
    {
        "name": "OpenAI GPTs",
        "type": "proprietary",
        "tracking_points": ["GPTs Store", "Actions API", "Revenue share"],
    },
    {
        "name": "MCP Protocol",
        "type": "open_standard",
        "tracking_points": ["Spec version", "Connector count", "Adoption"],
    },
    {
        "name": "LangChain",
        "type": "open_source",
        "tracking_points": ["Tool ecosystem", "Agent types"],
    },
    {
        "name": "CrewAI",
        "type": "open_source",
        "tracking_points": ["Multi-agent", "Task delegation"],
    },
]


def _load_baseline() -> dict[str, Any]:
    baseline_path = Path("data/competitive_baseline.json")
    if baseline_path.exists():
        return json.loads(baseline_path.read_text())
    return {"last_scan": "", "competitors": {}}


def _save_baseline(data: dict[str, Any]) -> None:
    Path("data/competitive_baseline.json").write_text(json.dumps(data, indent=2))


def cmd_scan() -> None:
    baseline = _load_baseline()
    now = datetime.now(timezone.utc).isoformat()

    for comp in _COMPETITORS:
        name = comp["name"]
        if name not in baseline["competitors"]:
            baseline["competitors"][name] = {
                "first_tracked": now,
                "last_updated": now,
                "points": {p: {"status": "unknown"} for p in comp["tracking_points"]},
            }

    baseline["last_scan"] = now
    _save_baseline(baseline)
    print(f"Scan complete. Tracking {len(_COMPETITORS)} competitors at {now}")


def cmd_report() -> None:
    baseline = _load_baseline()
    if not baseline.get("competitors"):
        print("No baseline data. Run 'scan' first.")
        sys.exit(1)

    print("=== Competitive Intelligence Report ===\n")
    print(f"Last scan: {baseline.get('last_scan', 'never')}\n")

    for name, data in baseline["competitors"].items():
        print(f"## {name}")
        print(f"  Tracked since: {data.get('first_tracked', '?')}")
        for point, status in data.get("points", {}).items():
            s = status.get("status", "unknown")
            icon = "✅" if s == "stable" else "🔄" if s == "changed" else "❓"
            print(f"  {icon} {point}: {s}")
        print()

    print("Comparison with SkillOS:")
    print("  - 5/25/70 Econ Model: ✅ unique (no competitor matches)")
    print("  - NegMarket: ✅ unique (no competitor matches)")
    print("  - MCP Connector: 🟡 parity target")
    print("  - LLM Integration: 🔴 gap (Anthropic/OpenAI ahead)")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: competitive_intel.py [scan|report]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "scan":
        cmd_scan()
    elif cmd == "report":
        cmd_report()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: Create config file**

Create `data/competitive_intel.yaml`:
```yaml
# Competitive Intelligence Config
scan_interval: "monthly"
tracked_competitors:
  - name: "Anthropic Cowork"
    urls:
      - "https://docs.anthropic.com/en/docs/build-with-claude/cowork"
  - name: "OpenAI GPTs"
    urls:
      - "https://platform.openai.com/docs/actions"
  - name: "MCP Protocol"
    urls:
      - "https://modelcontextprotocol.io"
comparison_dimensions:
  - name: "Economic Model"
    skillos: "5/25/70 (5% platform, 25% ecosystem, 70% contributor)"
  - name: "Failure Assetization"
    skillos: "NegMarket (negative sample market)"
  - name: "Protocol Support"
    skillos: "A2A + MCP + 3 reserved"
  - name: "Model Agnostic"
    skillos: "4-tier routing + Byzantine consensus"
  - name: "Skill Import"
    skillos: "Anthropic + OpenAI GPTs (v0.5.0)"
```

**Step 3: Test the script**

```bash
python3 scripts/competitive_intel.py scan && python3 scripts/competitive_intel.py report
```
Expected: Scan + report output with 5 competitors tracked

**Step 4: Commit**

```bash
git add scripts/competitive_intel.py data/competitive_intel.yaml
git commit -m "feat: add competitive intelligence automation script"
```

---

## Phase 5: 最终验证 (Week 8)

### Task 5.1: 全量回归测试

```bash
uv run pytest -v --tb=short --cov=skillos --cov-report=term-missing
```
Expected: All tests PASS, coverage >= 93%

### Task 5.2: 运行 KB 同步检查

```bash
python3 scripts/verify_kb_version_sync.py
```
Expected: All checks passed

### Task 5.3: 审计门禁验证

```bash
make audit  # if available, or run:
python3 scripts/verify_distribution.py && python3 scripts/arch_check.py && python3 scripts/verify_kb_sync.py
```

### Task 5.4: 最终提交

```bash
git log --oneline -20
git status
```

---

## 交付物清单

| Phase | Task | 交付物 | 预计工时 |
|-------|------|--------|---------|
| P1 | 1.1 | docs/01-README.md 修复 | 10 min |
| P1 | 1.2 | test_negmarket_api.py 10 test cases | 2 hr |
| P1 | 1.3 | 30-roadmap 对齐 | 30 min |
| P2 | 2.1 | MCP 真实连接器 + gateway 集成 | 4 hr |
| P2 | 2.2 | SLO/SLI 定义 + 错误预算 | 2 hr |
| P2 | 2.3 | LLM 意图分类集成 | 2 hr |
| P3 | 3.1 | PII ML 识别 + presidio | 2 hr |
| P3 | 3.2 | 跨平台 Skill 导入 | 2 hr |
| P4 | 4.1 | KB-code 同步 CI | 1 hr |
| P4 | 4.2 | 竞品情报脚本 | 30 min |
| P5 | 5 | 全量回归 + 最终验证 | 1 hr |
| | | **总计** | **~17 hr** |
