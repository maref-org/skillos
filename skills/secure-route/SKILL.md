# Skill: secure-route

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | secure-route |
| **版本** | 1.0.0 |
| **分类** | routing |
| **触发词** | "路由检查", "安全路由", "数据分类", "影响评估" |
| **优先级** | P0 |

## 功能描述

对用户请求进行安全路由决策：
- 自动分类数据级别（T0-T2）
- 评估影响级别（L1-L6）
- 选择合适的路由通道（快速/审慎/堡垒/堡垒+）
- 执行前路由治理检查
- 记录路由决策审计日志

## 触发场景

当用户说以下内容时触发：
- "这个请求怎么路由"
- "检查数据分类"
- "评估影响级别"
- "安全路由分析"

## 工具调用链

```
1. athena_classify — 数据分类和影响评估
2. maref_pre_route_check — H_c 控制熵查询
3. athena_route_request — 路由决策
4. maref_ingest_signal — 记录 ROUTE_DECISION 信号
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| text | string | 是 | 待路由的请求文本 |
| context | object | 否 | 附加上下文信息 |
| tier_override | integer | 否 | 覆盖数据级别（0-2） |

## 输出格式

```json
{
  "classification": {
    "tier": 1,
    "impact_level": 3,
    "mode": "thinking",
    "governance_required": true
  },
  "route": {
    "channel": "prudent",
    "providers": ["deepseek", "siliconflow"],
    "chain": "cross_model_verify",
    "governance_required": true
  },
  "governance": {
    "h_c": 0.45,
    "allowed": true,
    "signal_emitted": true
  }
}
```

## 路由矩阵

| 数据域 \ 影响面 | L1日常 | L2开源 | L3路线图 | L4安全边界 | L5内部商业 | L6合作伙伴 |
|---|---|---|---|---|---|---|
| **T0公开** | 🟢快速 | 🟢快速+脱敏 | 🟡审慎 | 🟡审慎+ | 🔴审慎++ | 🔴审慎++ |
| **T1内部敏感** | 🟠脱敏 | 🟠脱敏+去引用 | 🟠脱敏+审计 | 🔴堡垒 | 🔴堡垒+ | 🔴堡垒+HITL |
| **T2机密+PII** | 🔴堡垒 | ⛔拒绝+告警 | ⛔拒绝+告警 | 🔴堡垒+熔断 | 🔴堡垒++ | 🔴堡垒双审批 |

## 治理策略

- **FAIL_MODE**: closed（高安全场景阻断）
- **数据级别**: 动态评估
- **影响级别**: 动态评估

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| maref-governance-mcp | 8941 | 必需 |
| athena-orchestrator-mcp | 8150 | 必需 |

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 治理检查失败 | 根据 FAIL_MODE 决定阻断或降级 |
| 路由决策异常 | 记录审计日志，使用默认路由 |
| 信号发射失败 | 路由继续执行，记录告警 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-23 | 初始版本 |