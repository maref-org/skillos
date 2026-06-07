# Skill: ecosystem-audit

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | ecosystem-audit |
| **版本** | 1.0.0 |
| **分类** | governance |
| **触发词** | "生态健康检查", "系统审计", "健康状态", "审计报告" |
| **优先级** | P0 |

## 功能描述

对 Athena 生态系统进行全面健康检查，包括：
- MCP 服务器状态检测
- Agent 注册状态验证
- 信号总线流量分析
- 安全网关合规性检查
- 知识库完整性评估

## 触发场景

当用户说以下内容时触发：
- "检查生态健康状态"
- "运行系统审计"
- "生成健康报告"

## 工具调用链

```
1. maref_ingest_signal — 检查信号总线连接
2. maref_check_exfiltration — 安全合规扫描
3. athena_list_available_models — 模型可用性检查
4. athena_get_budget_status — 预算状态
5. athena_check_security_gate — Gate 0-5 安全检查
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| deep | boolean | 否 | 是否深度检查（默认: false） |
| include_metrics | boolean | 否 | 是否包含性能指标（默认: true） |

## 输出格式

```json
{
  "status": "healthy|degraded|critical",
  "summary": {
    "total_checks": 5,
    "passed": 4,
    "failed": 1
  },
  "components": {
    "maref-governance-mcp": {"status": "healthy", "latency_ms": 12},
    "athena-orchestrator-mcp": {"status": "healthy", "latency_ms": 8},
    "signal_bus": {"status": "healthy", "signal_count": 156}
  },
  "recommendations": ["修复 Gate 2 敏感路径问题"]
}
```

## 治理策略

- **FAIL_MODE**: open（降级运行）
- **数据级别**: T0（公开数据）
- **影响级别**: L1（日常局部）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| maref-governance-mcp | 8941 | 必需 |
| athena-orchestrator-mcp | 8150 | 必需 |
| signal-bus | 内部 | 必需 |

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| MCP 服务不可用 | 降级为本地检查，记录告警 |
| 网络超时 | 重试 3 次，间隔 2 秒 |
| 权限不足 | 返回错误信息，建议联系管理员 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-23 | 初始版本 |