# Skill: evaluate-oss-project

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | evaluate-oss-project |
| **版本** | 1.0.0 |
| **分类** | research |
| **触发词** | "评估开源项目", "代码质量分析", "集成还是蒸馏", "仓库评估" |
| **优先级** | P1 |

## 功能描述

对开源项目进行 9 维代码质量评估，做出四项决策：
- **集成**：代码质量 ≥ 0.7 + MIT/Apache → 封装为 MCP Tool
- **蒸馏**：代码质量 < 0.7 + 新颖算法 → 提取核心模式
- **参考**：代码质量 < 0.4 → KB 归档
- **暂缓**：安全扫描未通过 → 标记告警

## 触发场景

- "评估这个开源项目"
- "这个库值得集成吗"
- "分析代码质量"

## 工具调用链

```
1. percv_evaluate_repo — 克隆 + 9 维分析
2. percv_decide_integrate_or_distill — 四项决策
3. (if INTEGRATE) Register as MCP Tool → ToolRouter
4. (if DISTILL) Extract patterns → Knowledge Base
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| repo_url | string | 是 | Git 仓库 URL |
| depth | string | 否 | "fast"/"full"（默认: "fast"） |

## 输出格式

```json
{
  "evaluation": {
    "overall_score": 0.82,
    "dimensions": {"code_quality": 0.85, "docs": 0.78, "security": 0.80, "license": 0.95, "community": 0.75, "maintenance": 0.88, "tests": 0.70, "architecture": 0.85, "dependencies": 0.82}
  },
  "decision": "INTEGRATE",
  "confidence": 0.92,
  "action": "Wrap as MCP Tool, register in ToolRouter"
}
```

## 治理策略

- **FAIL_MODE**: open（降级运行）
- **数据级别**: T0（公开仓库）
- **影响级别**: L2（开源项目）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| percv-research-mcp | 8951 | 必需 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | Phase 3 SkillOS 版本 |