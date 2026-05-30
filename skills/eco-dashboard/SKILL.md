# Skill: eco-dashboard

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | eco-dashboard |
| **版本** | 1.0.0 |
| **分类** | operations |
| **触发词** | "生态全景", "仪表盘", "系统概览", "运营数据" |
| **优先级** | P2 |

## 功能描述

生成 Athena 生态全景仪表盘：
- 4 个 MCP 服务器状态
- Agent 注册和健康统计
- 信号总线流量趋势
- 预算消耗监控
- 外泄告警概览
- 路由决策分布

## 触发场景

- "显示生态仪表盘"
- "系统概览"
- "运营数据报告"
- "生态全景"

## 工具调用链

```
1. maref_ingest_signal — 信号总线状态
2. maref_check_exfiltration — 外泄告警数
3. athena_list_available_models — 模型池状态
4. athena_get_budget_status — 预算消耗
5. percv_vault_status — 知识库容量
6. mas_ts_get_agent_card — Agent 统计
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| format | string | 否 | "json"/"markdown"/"html"（默认: "markdown"） |
| include_trends | boolean | 否 | 是否包含趋势分析（默认: true） |

## 输出格式

```json
{
  "generated_at": "2026-05-27T10:00:00Z",
  "servers": {
    "maref-governance-mcp:8941": {"status": "healthy", "tools": 11, "signals_ingested": 423},
    "athena-orchestrator-mcp:8150": {"status": "healthy", "tools": 9, "routes_processed": 89},
    "percv-research-mcp:8951": {"status": "healthy", "tools": 21, "vault_signals": 96},
    "mas-ts-evaluation-mcp:8961": {"status": "healthy", "tools": 19, "evaluations_done": 12}
  },
  "agents": {"total": 5, "healthy": 4, "degraded": 1, "dead": 0},
  "budget": {"spent": 15.23, "limit": 50.0, "remaining": 34.77, "usage_pct": 30.5},
  "security": {"exfiltration_alerts": 0, "critical": 0, "gate_failures": 0}
}
```

## 治理策略

- **FAIL_MODE**: open（降级运行）
- **数据级别**: T0（运营数据）
- **影响级别**: L1（日常局部）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| maref-governance-mcp | 8941 | 必需 |
| athena-orchestrator-mcp | 8150 | 必需 |
| percv-research-mcp | 8951 | 可选 |
| mas-ts-evaluation-mcp | 8961 | 可选 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | 初始版本 |