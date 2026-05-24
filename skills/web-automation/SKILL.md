---
name: web-automation
description: "Browser automation via agent-browser CLI — navigate, snapshot, click, fill, submit, screenshot, extract"
version: "1.0.0"
autoApply: false
dependencies: []
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "browser automation"
  - "web navigation"
  - "agent browser"
  - "chrome automation"
  - "web scraping"
  - "fill form"
  - "click button"
  - "submit form"
  - "take screenshot"
  - "page snapshot"
input_schema:
  type: object
  properties:
    url:
      type: string
      description: "Target URL to navigate to"
    action:
      type: string
      enum: [navigate, snapshot, click, fill, submit, screenshot, extract, close]
      description: "Browser action to perform"
    selector:
      type: string
      description: "Element reference (e.g., @e1, @e2) or CSS selector"
    value:
      type: string
      description: "Value for fill/submit actions"
    output_path:
      type: string
      description: "Output path for screenshot/extract operations"
  required: [action]
output_schema:
  type: object
  properties:
    success:
      type: boolean
    data:
      type: object
    snapshot_refs:
      type: array
      items:
        type: string
sla:
  target_success_rate: 0.95
  max_latency_ms: 15000
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes: "Initial version — agent-browser CLI operation encapsulation, SocialPublisher fallback integration"
---

# Skill: web-automation

## Overview

Browser automation via agent-browser CLI (Vercel Labs, Rust + CDP). Provides a programmatic interface for Chrome browser control: navigation, element interaction, content extraction, and visual capture. Serves as the Web execution layer (L1) for multi-agent CLI operating systems.

## When to Use

Trigger when:
- Need to navigate to a website and interact with its UI
- Need to fill and submit web forms programmatically
- Need to take screenshots of web pages
- Need to extract structured content from web pages
- Social media platform API is unavailable → fallback to browser simulation

## Core Instructions

### Command Reference

```bash
# Session management
agent-browser doctor --json              # Health check
agent-browser open <url>                 # Navigate to URL (starts session)
agent-browser close                      # End session

# Page inspection
agent-browser snapshot --json            # Full DOM snapshot with refs
agent-browser snapshot -i --json         # Interactive elements only
agent-browser screenshot                 # Screenshot (viewport)
agent-browser screenshot --annotate      # Annotated with element refs
agent-browser screenshot --full          # Full page screenshot

# Element interaction
agent-browser click <ref>                # Click element by ref (@e1)
agent-browser fill <ref> <value>         # Fill input by ref
agent-browser submit                     # Submit current form
agent-browser press <key>                # Press keyboard key
agent-browser scroll <direction>         # Scroll page (up/down)

# Content extraction
agent-browser eval <js>                  # Execute JavaScript
agent-browser get text <ref>             # Get element text
agent-browser get value <ref>            # Get input value
agent-browser get title                  # Get page title

# Batch pipeline
agent-browser run batch.json             # Execute multi-command sequence
agent-browser run --pipe < commands.txt  # Pipe mode
```

### Session Management

- Sessions persist across commands by default
- Cookies and local storage maintained within session
- Session encryption: AES-256-GCM before disk storage
- Session timeout: 30 minutes idle → auto-close
- Session file location: `~/.agent-browser/sessions/{hash}.enc`

### Element Reference System

After `snapshot -i`, elements are assigned refs like `@e1`, `@e2`, etc. These refs are used for subsequent interactions:

```
$ agent-browser snapshot -i --json
{
  "elements": [
    {"ref": "@e1", "tag": "input", "type": "text", "placeholder": "Search..."},
    {"ref": "@e2", "tag": "button", "text": "Submit"},
    {"ref": "@e3", "tag": "a", "text": "Documentation"}
  ]
}

$ agent-browser fill @e1 "agent automation"
$ agent-browser click @e2
```

### Batch Pipeline Format

```json
{
  "commands": [
    {"action": "open", "url": "https://example.com/login"},
    {"action": "snapshot", "interactive": true},
    {"action": "fill", "ref": "@e1", "value": "user@example.com"},
    {"action": "fill", "ref": "@e2", "value": "password"},
    {"action": "click", "ref": "@e3"},
    {"action": "screenshot", "output": "/tmp/result.png"},
    {"action": "close"}
  ]
}
```

## Social Media Fallback Integration

When a platform's official API is rate-limited, unavailable, or non-existent (e.g., 小红书, 抖音), use agent-browser as fallback:

```python
async def publish_with_fallback(content: PlatformContent) -> PublishResult:
    try:
        result = await platform_api_publish(content)
    except (RateLimitError, ApiUnavailableError):
        logger.warning(f"API unavailable for {content.platform}, falling back to browser")
        result = await browser_simulate_publish(content)
    return result
```

### Platform-Specific Browser Automation

| Platform | Strategy | Key Interactions |
|----------|----------|-----------------|
| 小红书 | Playwright/agent-browser | Login → Create Note → Upload Image → Fill Title/Desc → Publish |
| 抖音 | Playwright/agent-browser | Login → Creator Center → Upload Video → Fill Title/Hashtags → Publish |
| B站 | Playwright/agent-browser | Login → Upload → Select Video → Fill Info → Submit Review |

## Security

- Only whitelisted domains allowed in production mode
- Credentials never stored in plaintext; use environment variables or encrypted vault
- Screenshot output paths sanitized to prevent path traversal
- `eval` operations require HumanGate confirmation in production
- All browser sessions run in isolated profile directories

## Error Recovery

| Error | Cause | Recovery |
|-------|-------|----------|
| agent-browser: command not found | Not installed | `npm install -g agent-browser && agent-browser install` |
| CDP connection refused | Chrome not running or port conflict | `agent-browser doctor` to diagnose |
| Element ref not found (@eX) | Page changed since snapshot | Re-snapshot and re-identify element |
| Timeout | Slow page load or network issue | Retry with increased timeout (--timeout 30) |

## Examples

### Login Flow
```bash
agent-browser open https://example.com/login
agent-browser snapshot -i --json
# Identify username field → @e1, password → @e2, submit → @e3
agent-browser fill @e1 "$LOGIN_USER"
agent-browser fill @e2 "$LOGIN_PASS"
agent-browser click @e3
agent-browser screenshot --output /tmp/logged_in.png
```

### Content Extraction
```bash
agent-browser open https://github.com/trending
agent-browser snapshot --json | jq '.elements[] | select(.tag=="article")'
agent-browser get text @e1
```

### Multi-Page Workflow
```bash
agent-browser open https://platform.com/dashboard
agent-browser click @e5         # Click "Create Post"
agent-browser fill @e1 "Title"  # Fill title
agent-browser fill @e2 "Body"   # Fill body
agent-browser click @e3         # Upload media
agent-browser click @e4         # Publish
agent-browser screenshot --output /tmp/published.png
agent-browser close
```

## Testing

- Run `agent-browser doctor --json` — all checks pass
- Snapshot returns valid element refs
- Click/fill/submit sequence completes without errors
- Screenshot produces valid image file
- Session persists across multiple commands
- Batch pipeline executes all commands in order

## Changelog

See frontmatter.
