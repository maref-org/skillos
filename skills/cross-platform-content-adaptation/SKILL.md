---
name: cross-platform-content-adaptation
description: "跨平台内容格式适配 — 12 平台字符限制、Hashtag 策略、智能截断算法、媒体规格、最佳发布时间。Invoke 当需要将一份内容适配到多个社媒平台、调整文案长度、选择标签、裁剪媒体格式。"
version: "1.0.0"
autoApply: false
dependencies:
  - multi-agent-media-orchestration
platforms:
  - claude
  - opencode
triggers:
  - "内容适配"
  - "跨平台发布"
  - "格式转换"
  - "社媒适配"
  - "Hashtag"
  - "字符限制"
  - "内容分发"
  - "platform adaptation"
  - "multi-platform format"
input_schema:
  type: object
  properties:
    source_text:
      type: string
    platforms:
      type: array
      items:
        type: string
    media_paths:
      type: array
      items:
        type: string
sla:
  target_success_rate: 0.95
  max_latency_ms: 5000
changelog:
  - version: "1.0.0"
    date: "2026-05-08"
    changes: "Initial version — 12 platform adaptation rules"
---

# Skill: cross-platform-content-adaptation

## Overview

将一份源内容自动适配到 12 个社媒平台的完整规则集。包括字符限制、Hashtag 策略、媒体格式约束、最佳发布时间。

代码位置: `agents/content_distribution_agent/platform_adapter.py`

---

## 平台约束矩阵

| 平台 | 最大字符 | 最大媒体 | 视频最长 | 纵横比 | 优先级 |
|------|:---:|:---:|:---:|------|:---:|
| Twitter/X | 280 | 4 | 140s | 16:9 | P0 |
| GitHub | — | — | — | markdown | P0 |
| Discord | 2000 | 10 | — | webhook | P0 |
| LinkedIn | 3000 | — | 600s | 16:9 | P1 |
| YouTube | — | — | — | 16:9 | P1 |
| Bilibili | — | — | — | 16:9 | P1 |
| Instagram | — | — | 90s (Reels) | 9:16 | P2 |
| 小红书 | 1000 | — | 300s | 3:4 | P2 |
| 抖音 | — | — | 180s | 9:16 | P2 |
| TikTok | — | — | 180s | 9:16 | P2 |
| Threads | 500 | 10 | — | 9:16 | P2 |
| 微博 | 2000 | 9 | — | 16:9 | P3 |

代码: `tools/connectors/base_connector.py` → `PLATFORM_RULES`

---

## Hashtag 策略

### 按平台分类

```python
PLATFORM_HASHTAGS = {
    "twitter": ["#OpenHuman", "#AI", "#OpenSource", "#CarbonSilicon"],
    "linkedin": ["#OpenHuman", "#AIAgent", "#OpenSource", "#Innovation"],
    "xiaohongshu": ["#OpenHuman", "#AI", "#开源项目", "#科技"],
    "douyin": ["#OpenHuman", "#AI", "#科技"],
    "weibo": ["#OpenHuman", "#AI开源", "#科技"],
    "jike": ["#OpenHuman"],
    # github, discord: 无 hashtag 惯例
}
```

### 规则

1. 基础标签 + 内容标签(source.tags), 去重后取前 5 个
2. 中文平台用中文标签, 英文字台用英文标签
3. 开源项目在 technical 平台偏技术标签, 在 lifestyle 平台偏概念标签

---

## 智能截断算法

```python
def _smart_truncate(text: str, max_chars: int) -> str:
    """在句子边界处截断, 不切断完整句子"""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars - 3]
    # 找最后一个句号/感叹号/换行
    last = max(
        truncated.rfind("。"), truncated.rfind(". "),
        truncated.rfind("！"), truncated.rfind("\n"),
    )
    if last > max_chars // 2:    # 后半段有边界
        return truncated[:last + 1]
    return truncated + "..."      # 强制截断
```

---

## 媒体格式要求

### 视频多分辨率输出

```python
PLATFORM_VIDEO_SPECS = {
    "twitter": {"max_duration": 140, "aspect": "16:9", "suffix": "_twitter"},
    "bilibili": {"min_duration": 15, "aspect": "16:9", "suffix": "_bili"},
    "tiktok": {"max_duration": 180, "aspect": "9:16", "suffix": "_tt"},
    "instagram_reels": {"max_duration": 90, "aspect": "9:16", "suffix": "_reel"},
    "xiaohongshu": {"max_duration": 300, "aspect": "3:4", "suffix": "_xhs"},
}
```

FFmpeg 命令:
```bash
ffmpeg -i master.mp4 -c:v libx264 -preset fast -crf 23 \
    -vf "scale='min(720,iw)':-2" platform_variant.mp4
```

---

## 最佳发布时间窗口

| 平台 | 最佳窗口 | 最大/天 |
|------|---------|:---:|
| Twitter | 周三-周五 15:00-18:00 UTC | 5 |
| LinkedIn | 周二-周四 08:00-10:00 UTC | 2 |
| GitHub | 任意 15:00-20:00 UTC | 3 |
| YouTube | 周六-周日 12:00-16:00 UTC | 1 |
| Bilibili | 每日 12:00-14:00 CST | 2 |
| 小红书 | 每日 07:00-09:00 CST | 3 |
| 抖音 | 每日 18:00-21:00 CST | 3 |
| Instagram | 每日 11:00-13:00 UTC | 2 |
| Discord | 每日 10:00-22:00 UTC | 10 |
| 即刻 | 每日 10:00-18:00 CST | 3 |

---

## 分发优先级

```python
PLATFORM_DISPATCH_PRIORITY = [
    "github",    # 源码仓库, 先发
    "twitter",   # 英文首发
    "linkedin",  # B端背书
    "discord",   # 社区公告
    "youtube", "bilibili",  # 视频深度内容
    "threads", "instagram",  # 视觉平台
    "xiaohongshu", "douyin", "tiktok",  # 破圈平台
    "weibo", "jike",  # 国内社区
]
```

先从核心阵地(GitHub/Twitter)发布, 再扩展到破圈平台。同平台内容间隔 ≥2 小时。

---

## 使用示例

```python
from agents.content_distribution_agent import PlatformAdapter, SourceContent

adapter = PlatformAdapter()
src = SourceContent(
    content_id="ann_001",
    content_type="announcement",
    title="OpenHuman v0.1",
    text="We are excited to announce... " * 20,
    tags=["AI", "OpenSource"],
)

for p in ["twitter", "linkedin", "xiaohongshu"]:
    pc = adapter.adapt(src, p)
    print(f"{p}: {len(pc.text)} chars, {pc.hashtags}")
    # twitter: 207 chars, ['#OpenHuman', '#AI', '#OpenSource']
    # linkedin: 832 chars, ['#OpenHuman', '#AIAgent', '#OpenSource', '#Innovation', '#AI']
    # xiaohongshu: 832 chars, ['#OpenHuman', '#AI', '#开源项目', '#科技', '#OpenSource']
```

---

## Changelog

See frontmatter.
