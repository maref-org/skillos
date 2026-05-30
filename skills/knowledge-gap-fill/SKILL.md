# Skill: knowledge-gap-fill

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | knowledge-gap-fill |
| **版本** | 1.0.0 |
| **分类** | knowledge |
| **触发词** | "知识库缺口", "补全知识库", "知识扫描", "领域缺失" |
| **优先级** | P2 |

## 功能描述

扫描知识库缺失领域和过时模式，推断信息缺口并建议研究优先级：
- 领域缺失检测
- 过时模式标记
- 缺口置信度评估
- 补全来源推荐

## 触发场景

- "扫描知识库空白"
- "AI agent 领域有什么缺失"
- "知识库缺口分析"

## 工具调用链

```
1. percv_scan_kb_gaps — 领域缺失扫描
2. percv_infer_gaps — 信息缺口推断
3. (可选) percv_collect_osint — 补全缺口信息
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| domain | string | 否 | 特定领域扫描 |
| min_confidence | float | 否 | 最低置信度阈值（默认: 0.5） |

## 输出格式

```json
{
  "gaps": 5,
  "high_priority": 2,
  "results": [
    {"domain": "ai_agent", "gap": "多Agent协作协议", "confidence": 0.85, "suggested_sources": ["arxiv", "github"]},
    {"domain": "security", "gap": "LLM供应链安全", "confidence": 0.78, "suggested_sources": ["owasp", "nist"]}
  ]
}
```

## 治理策略

- **FAIL_MODE**: open（降级运行）
- **数据级别**: T0（公开知识）
- **影响级别**: L1（日常局部）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| percv-research-mcp | 8951 | 必需 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | Phase 3 SkillOS 版本 |