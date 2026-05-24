---
name: content-calendar
description: "Content calendar and scheduling system for cross-platform social media publishing"
version: "1.1.0"
autoApply: false
dependencies:
  - cross-platform-content-adaptation
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "content calendar"
  - "content schedule"
  - "publishing schedule"
  - "social media calendar"
  - "cross platform schedule"
  - "content planning"
input_schema:
  type: object
  properties:
    content_type:
      type: string
      enum: [announcement, tutorial, story, milestone, video, general]
    source_content_id:
      type: string
    platforms:
      type: array
      items:
        type: string
sla:
  target_success_rate: 0.95
  max_latency_ms: 5000
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes: "Initial version — SQLite-based content calendar with conflict detection"
---

# Skill: content-calendar

## Overview

Cross-platform content calendar system for multi-agent media workflows. Provides SQLite-based scheduling, conflict detection, and cross-platform timing optimization. Supports 12 target platforms.

## When to Use

- Scheduling new content for publication
- Checking for scheduling conflicts
- Optimizing publish times across platforms
- Tracking content status (draft → scheduled → published → failed)

## Data Model

```python
ContentCalendarEntry:
    id: str
    content_type: str          # announcement / tutorial / story / milestone / video
    source_content_id: str     # reference to source content
    platform_variants: dict    # per-platform adapted versions
    scheduled_at: dict         # per-platform publish times
    status: str                # draft / scheduled / published / failed
    published_ids: dict        # per-platform post IDs
    metrics: dict              # per-platform post-publish metrics
    created_at: datetime
    updated_at: datetime
```

## Core Operations

### Schedule Content
```python
entry = ContentCalendarEntry(
    id=generate_id(),
    content_type="announcement",
    source_content_id="src_001",
    scheduled_at={"twitter": "2026-05-10T09:00:00Z", "github": "2026-05-10T09:05:00Z"},
    status="scheduled",
)
```

### Conflict Detection
- Same platform: minimum 2-hour interval between posts
- Cross-platform: stagger by 5-minute intervals
- Priority ordering: GitHub → Twitter → LinkedIn → Discord → Others

### Status Transitions
```
draft → scheduled → published → (metrics collected)
                  → failed → (retry or manual fix)
```

## Platform Timing Rules

| Platform | Optimal Window (UTC) | Max Posts/Day |
|----------|---------------------|:---:|
| Twitter | 15:00-18:00 (Wed-Fri) | 5 |
| LinkedIn | 08:00-10:00 (Tue-Thu) | 2 |
| GitHub | 15:00-20:00 (any day) | 3 |
| YouTube | 12:00-16:00 (Sat-Sun) | 1 |
| B站 | 12:00-14:00, 18:00-20:00 (daily) | 2 |
| 小红书 | 07:00-09:00, 20:00-22:00 | 3 |
| 抖音 | 12:00-13:00, 18:00-21:00 | 3 |
| Instagram | 11:00-13:00, 19:00-21:00 | 2 |
| Discord | 10:00-22:00 (any day) | 10 |
| Threads | 12:00-15:00 (any day) | 3 |
| 微博 | 08:00-10:00, 20:00-22:00 | 5 |
| TikTok | 12:00-14:00, 19:00-21:00 | 3 |

## Storage

SQLite database at: `./data/content_calendar.db` (configurable via `CONTENT_CALENDAR_DB` env var)

## Examples

### Schedule a Launch Day Post
```python
entry = calendar.schedule(
    content_type="announcement",
    source_content_id="launch_001",
    platforms=["github", "twitter", "linkedin", "discord"],
    base_time="2026-06-01T09:00:00Z",
)
# Auto-generates staggered times:
#   github: 09:00, twitter: 09:05, linkedin: 09:10, discord: 09:15
```

## Changelog

### v1.1.0 (2026-05-08)
- 添加智能时段建议算法 (`suggest_time`)
- 添加平台最佳时间窗口配置 (12平台)
- 集成 ContentDistributionAgent 的 DispatchEngine

### v1.0.0 (2026-05-06)
See frontmatter.
