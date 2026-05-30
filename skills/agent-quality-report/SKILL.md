# Skill: agent-quality-report

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | agent-quality-report |
| **版本** | 1.0.0 |
| **分类** | evaluation |
| **触发词** | "Agent质量报告", "评估报告", "Agent Card更新", "PQS检查" |
| **优先级** | P1 |

## 功能描述

生成多Agent质量评估报告，包括：
- 5 层评估（静态审计→推理指标→动作指标→E2E指标→MAS维度）
- Agent Card 更新（PQS/TCR/PIR/BFT）
- 路由权重联动
- 退化检测（prompt rot）

## 触发场景

- "生成 agent 质量报告"
- "检查 agent 是否有退化"
- "更新路由权重"
- "Agent 评估"

## 工具调用链

```
1. mas_ts_evaluate_full — 5 层全量评估
2. mas_ts_get_agent_card — 获取 PQS/TCR/PIR/BFT
3. mas_ts_detect_prompt_rot — 退化检测
4. maref_update_trust_score — 路由权重联动
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | Agent 标识符 |
| mode | string | 否 | "fast"/"full"（默认: "full"） |
| update_weights | boolean | 否 | 是否更新路由权重（默认: true） |

## 输出格式

```json
{
  "agent_id": "claude_code",
  "evaluation": {
    "overall_score": 87,
    "grade": "B+",
    "layers": {
      "layer1": {"score": 92, "name": "Static Audit"},
      "layer2": {"score": 85, "name": "Inference Metrics"},
      "layer3": {"score": 80, "name": "Action Metrics"},
      "layer4": {"score": 88, "name": "E2E Metrics"},
      "layer5": {"score": 90, "name": "MAS Dimension"}
    }
  },
  "agent_card": {"PQS": 0.92, "TCR": 0.87, "PIR": 0.85, "BFT": 0.90},
  "trust_score": 0.94,
  "weight_update": "applied",
  "recommendations": ["Improve action metrics coverage"]
}
```

## 治理策略

- **FAIL_MODE**: open（降级运行）
- **数据级别**: T1（内部指标）
- **影响级别**: L3（路线图）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| mas-ts-evaluation-mcp | 8961 | 必需 |
| maref-governance-mcp | 8941 | 必需 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | 初始版本 |