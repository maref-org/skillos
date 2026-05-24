---
name: universal-cli-operator
description: "Unified CLI operator skill for multi-platform automation (Web/Desktop/Mobile/Social)"
version: "1.0.0"
autoApply: false
dependencies:
  - web-automation
  - universal-cli-operator
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "operate browser"
  - "automate web"
  - "desktop automation"
  - "mobile agent"
  - "social media post"
  - "multi-platform"
  - "cli operator"
  - "universal cli"
  - "cross platform automation"
input_schema:
  type: object
  properties:
    target:
      type: string
      description: "Target URL, platform name, app name, or task description"
    platform:
      type: string
      enum: [web, social, desktop, mobile]
      description: "Target platform type"
    action:
      type: string
      description: "Action to perform (navigate, snapshot, click, fill, submit, screenshot, extract)"
  required: [target]
output_schema:
  type: object
  properties:
    result:
      type: object
    platform_used:
      type: string
    session_id:
      type: string
sla:
  target_success_rate: 0.90
  max_latency_ms: 30000
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes: "Initial version — 4-platform tool matrix + decision rules + security policies"
---

# Skill: universal-cli-operator

## Overview

Unified CLI operator that routes automation tasks across 4 platform types: Web (agent-browser), Social (Agent-Reach), Desktop (CLI-Anything), and Mobile (ADB Agent). Acts as the single entry point for all CLI-driven platform automation.

## When to Use

Trigger when a task involves:
- Opening/navigating/interacting with a web URL
- Posting content to social media platforms
- Automating desktop application workflows
- Controlling a connected mobile device (Z Flip3)
- Cross-platform coordinated operations

## 4-Platform Tool Matrix

| Platform | Tool | Command Pattern | Strengths |
|----------|------|----------------|-----------|
| **Web** | agent-browser | `agent-browser {action} [url]` | CDP-based Chrome automation, snapshot refs, session persistence |
| **Social** | Agent-Reach | `agent-reach {action} --platform {name}` | 10+ social platform coverage, safe mode, dry-run |
| **Desktop** | CLI-Anything | (future) Claude Code plugin | Desktop app automation via community harness |
| **Mobile** | ADB Agent | `python mobile_agent.py "{task}" --real` | ADB-based device control, Vision system |

## Decision Rules

Route tasks based on target pattern matching:

```
URL pattern (http/https)              → Web: agent-browser
Social media platform mention         → Social: Agent-Reach
Desktop app / file / window mention   → Desktop: CLI-Anything (future)
Mobile app / phone / device mention   → Mobile: ADB Agent
Ambiguous / cross-platform            → SmartOrchestrator routing
```

### Platform Keyword Mapping

```yaml
web_keywords:
  - url, website, page, browser, chrome, login, form, download
  - http://, https://, .com, .org, .io

social_keywords:
  - twitter, x.com, linkedin, instagram, facebook, discord
  - tiktok, youtube, bilibili, 小红书, 微博, 抖音
  - post, tweet, publish, share, social, 发布

desktop_keywords:
  - file, folder, window, application, desktop, app
  - open file, save as, export, import

mobile_keywords:
  - phone, device, mobile, android, z flip, zflip
  - app on phone, mobile app, 手机
```

## Security Policies

### Session Security (agent-browser)
- All session cookies encrypted with AES-256-GCM before disk storage
- Session files permissions: 0600 (owner read/write only)
- Auto-clean expired sessions (>24h idle)

### Domain Restrictions (agent-browser)
- Default: allow-list mode — only whitelisted domains navigable
- Whitelist management: `<PROJECT_ROOT>/config/browser_allowed_domains.yaml`
- Production domains must be pre-approved via HumanGate

### Social Media Safety (Agent-Reach)
- Always prefer `--safe` mode (no destructive operations)
- Use `--dry-run` for first-time platform verification
- Dedicated test accounts, never production credentials
- Post frequency: max 3 posts/hour/platform to avoid rate limits

### Sensitive Operation Confirmation
- Operations requiring HITL confirmation: eval, download, file_upload, payment
- Confirmation flow: HumanGate → iOS Bark notification → explicit approval
- Timeout: 5 minutes without confirmation → auto-reject

## Error Handling

| Error Type | Strategy | Fallback |
|------------|----------|----------|
| agent-browser unavailable | Log + notify | Fallback to HTTP request via Python aiohttp |
| Social platform API rate limit | Exponential backoff (1s, 4s, 16s) | Queue for next cycle |
| ADB device disconnected | 3x retry (1s interval) | Notify user to reconnect device |
| CDP bridge unavailable | Fallback pure ADB | Skip web-dependent operations |

## State Integration

All CLI operations feed into the governance system:
- Each operation generates a state transition event
- Budget tracking: operations consume from budget_engine allocations
- Failure states trigger automatic escalation per monitoring rules

## Examples

### Web: Navigate and Capture
```bash
agent-browser open https://github.com
agent-browser snapshot -i --json
agent-browser screenshot --annotate --output /tmp/github.png
```

### Social: Post to Twitter
```bash
agent-reach post --platform twitter \
  --text "Check out our project: AI-powered workflow automation" \
  --media /tmp/teaser.mp4 \
  --safe
```

### Mobile: Open Settings
```bash
cd <PROJECT_ROOT>/agent_system
python mobile_agent.py "打开设置" --real --verbose
```

### Cross-Platform: Publish Video Everywhere
```bash
python -m agents.content_distribution_agent.dispatch \
  --source /tmp/demo_60s.mp4 \
  --platforms twitter,youtube,bilibili,linkedin,discord
```

## Testing

- Verify agent-browser doctor passes all checks
- Verify Z Flip3 --check-real-config passes
- Test URL pattern routing → agent-browser selected
- Test social media mention routing → Agent-Reach selected
- Test security: blocked domain is rejected
- Test session persistence across multiple agent-browser commands

## Changelog

See frontmatter.
