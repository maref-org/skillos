---
name: multi-agent-media-orchestration
description: "多Agent媒体中心编排 — 6 Agent Pipeline 串联、SourceContent 标准化、dry-run 安全测试模式、跨 Agent 错误恢复。Invoke 当需要搭建多Agent媒体工作流、内容生产→分发→分析Pipeline、Agent编排架构设计。"
version: "1.0.0"
autoApply: false
dependencies:
  - content-calendar
  - cross-platform-content-adaptation
platforms:
  - claude
  - opencode
triggers:
  - "多Agent媒体"
  - "Agent 编排"
  - "内容分发Pipeline"
  - "媒体Pipeline"
  - "视频生产→分发"
  - "content pipeline"
  - "media orchestrator"
  - "分发调度"
  - "Agent pipeline"
input_schema:
  type: object
  properties:
    content_type:
      type: string
      enum: [announcement, tutorial, story, video, milestone]
    platforms:
      type: array
      items:
        type: string
    dry_run:
      type: boolean
      description: "安全预览模式, 不做真实发布"
sla:
  target_success_rate: 0.90
  max_latency_ms: 30000
changelog:
  - version: "1.0.0"
    date: "2026-05-08"
    changes: "Initial version — 6 Agent Pipeline 架构 + 端到端验证"
---

# Skill: multi-agent-media-orchestration

## Overview

多Agent媒体中心是 OpenHuman 的社媒运营引擎。6 个 Agent 组成三级 Pipeline:

```
内容生产层         内容分发层        数据分析层
VideoAgent    →   DistributionAgent  →  AnalyticsAgent
(视频/I2V)        (12平台适配+调度)     (跨平台指标+ROI)
                    ↗  (via StarTracker)
                    ↗  (via CrisisAgent)
                    ↗  (via ABTesting)
```

---

## Pipeline 数据流

### SourceContent (统一源格式)

```python
from agents.content_distribution_agent import SourceContent

src = SourceContent(
    content_id="launch_001",
    content_type="announcement",
    title="OpenHuman v0.1 Released",
    text="Full announcement text...",
    summary="One-liner summary for previews",
    media_paths=["/path/to/video.mp4", "/path/to/cover.jpg"],
    links=["https://github.com/openhuman-ai/openhuman"],
    tags=["AI", "OpenSource", "CarbonSilicon"],
)
```

### 适配后 → PlatformContent

```python
from agents.content_distribution_agent import PlatformAdapter
adapter = PlatformAdapter()
variants = adapter.adapt_all(src, ["twitter", "linkedin", "discord"])

# twitter: 207 chars (auto-truncated from 832)
# linkedin: 832 chars (full text)
# discord: 832 chars (full text, Discord markdown)
```

### 分发 → DispatchResult

```python
from agents.content_distribution_agent import DispatchEngine
engine = DispatchEngine()
result = await engine.dispatch(variants, parallel=True)
# result.success_rate → 0.67 (2/3 if one platform fails)
```

---

## 端到端调用示例

### 完整 Pipeline (dry-run 安全模式)

```python
import asyncio
from agents import (
    ContentDistributionAgent, HappyHorseVideoAgent,
    AnalyticsAgent, ABExperiment,
)

async def full_pipeline():
    # 1. 视频生产
    video_agent = HappyHorseVideoAgent()
    scenes = [video_agent.create_scene_plan("Awakening", "epic", "...")]
    results = video_agent.generate_scenes(scenes)
    package = video_agent.assemble(results)

    # 2. 内容分发
    dist_agent = ContentDistributionAgent()
    src = dist_agent.create_source(
        content_id="vid_001", content_type="video",
        title="Athena Awakens", text="Watch Athena rise...",
        media_paths=[str(package.master_video)],
        tags=["AI", "Athena"],
    )
    # dry_run=True = 安全预览, 不发帖
    result = await dist_agent.distribute(
        src, ["twitter", "youtube", "bilibili", "discord"],
        dry_run=True,
    )
    for p, r in result.results.items():
        print(f"{p}: {'✓' if r['success'] else '✗'} — {r.get('text_preview', '')[:50]}")

    # 3. 分析
    analytics = AnalyticsAgent()
    dashboard = analytics.dashboard()
    return dashboard

asyncio.run(full_pipeline())
```

### 仅分发 (已有点素材)

```python
agent = ContentDistributionAgent()
src = agent.create_source(
    content_id="ann_001", content_type="announcement",
    title="OpenHuman Launch", text="Full text...",
    tags=["AI"],
)
result = await agent.distribute(src, ["twitter", "github", "discord"])
print(f"Success: {result.success}/{result.total}")
```

---

## 错误处理策略

| 层级 | 策略 |
|------|------|
| 单个平台失败 | 不影响其他平台, 记录到 result.results |
| 连接器不存在 | 返回 NotImplementedError, 不崩溃 |
| 认证失败 | 跳过该平台, 继续其他 |
| 全局异常 | DispatchResult 捕获, 不传播 |

---

## Agent 位置映射

| Agent | 代码位置 |
|-------|---------|
| ContentDistributionAgent | `agents/content_distribution_agent/agent.py` |
| HappyHorseVideoAgent | `agents/video_content_agent/agent.py` |
| AnalyticsAgent | `agents/analytics_agent/__init__.py` |
| ABExperiment | `agents/ab_testing.py` |
| CrisisAgent | `agents/crisis_agent/__init__.py` |
| StarTracker | `agents/star_tracker.py` |

---

## 测试清单

- [ ] dry_run 模式: 不产生真实发布
- [ ] parallel dispatch: 多平台同时发帖
- [ ] 单平台失败不影响其他
- [ ] SourceContent → PlatformContent 适配正确 (字符数/标签)
- [ ] 完整 Pipeline: 视频→分发→分析

## Changelog

See frontmatter.
