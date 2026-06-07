# Skill: research-competitor

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | research-competitor |
| **版本** | 1.0.0 |
| **分类** | research |
| **触发词** | "研究X公司技术栈", "竞品分析", "OSINT研究", "技术趋势分析" |
| **优先级** | P1 |

## 功能描述

使用 12 种公开源对竞品公司进行 OSINT 研究：
- 多源碎片收集（GitHub, HN, Crunchbase, arXiv, 专利库）
- 关联验证（≥3 源 → 置信度 ≥ 0.80）
- 演化轨迹合成（2 年趋势）
- 信息缺口推断

## 触发场景

- "研究 OpenAI 技术栈"
- "分析 Google 最新动态"
- "竞品技术对比"
- "OSINT 信息收集"

## 工具调用链

```
1. percv_collect_osint — 12 源碎片收集
2. percv_cross_reference — 关联验证
3. percv_synthesize_trajectory — 演化轨迹合成
4. percv_infer_gaps — 缺口推理
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| company | string | 是 | 竞品公司名称 |
| depth | string | 否 | "overview"/"deep"/"full"（默认: "deep"） |
| time_range | string | 否 | "1y"/"2y"/"5y"（默认: "2y"） |
| sources | array | 否 | 指定数据源列表 |

## 输出格式

```json
{
  "report": "## OpenAI 技术栈分析\n...",
  "verified_facts": 23,
  "confidence_score": 0.87,
  "knowledge_gaps": ["缺少内部定价模型", "私有部署细节"],
  "trajectory": {
    "2024-2025": "GPT-4o → o1 → o3",
    "2025-2026": "Operator agent → 多模态深化"
  }
}
```

## 治理策略

- **FAIL_MODE**: open（降级运行）
- **数据级别**: T0（公开数据）
- **影响级别**: L2（开源项目）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| percv-research-mcp | 8951 | 必需 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | Phase 3 SkillOS 版本 |