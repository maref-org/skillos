---
name: trend-fetch
description: "Real-time trend and hot topic fetching for content strategy optimization"
version: "1.0.0"
autoApply: false
dependencies: []
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "trend fetch"
  - "hot topic"
  - "trending topics"
  - "real-time trends"
  - "social trends"
  - "热点追踪"
input_schema:
  type: object
  properties:
    sources:
      type: array
      items:
        type: string
      enum: [twitter_trends, github_trending, google_trends, news]
    limit:
      type: integer
      default: 10
sla:
  target_success_rate: 0.90
  max_latency_ms: 10000
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes: "Initial version — Twitter Trends + GitHub Trending + Google Trends integration"
---

# Skill: trend-fetch

## Overview

Real-time trend fetching from multiple sources to feed the content strategy engine. Integrates with the content planning pipeline to ensure social media content stays relevant.

## Data Sources

| Source | API | Update Frequency |
|--------|-----|:---:|
| Twitter Trends | X API v2 trends/place | 15 minutes |
| GitHub Trending | github.com/trending (scrape) | 1 hour |
| Google Trends | pytrends library | 1 hour |
| public-apis News | Community API index | varies |

## When to Use

- Before content planning sessions
- When contentAgent requests topic suggestions
- Daily trend digest generation
- Crisis monitoring (negative trend detection)
