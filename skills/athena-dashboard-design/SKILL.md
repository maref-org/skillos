---
name: athena-dashboard-design
description: Use when building live data dashboards, agent control consoles, system monitoring UI, real-time operations panels, or any multi-panel web UI with dark mode, collapsible sidebars, and API-driven data. Use when user asks for "仪表板", "监控看板", "Agent 控制台", or "操作界面".
---

# Athena Dashboard Design System

> Extracted from Athena UI v1.1 — 碳硅共生 Agent 平台. Apple-inspired design system for live data dashboards.
> **Open Design compatible:** DESIGN.md follows the 9-section schema from awesome-design-md.

## When to Use

- Building a live data dashboard with real-time metrics
- Creating an agent control console with task queue, status cards, monitoring panels
- UI needs three-column layout with collapsible sidebars
- Requirements include dark mode, CSS variable theming, zoom resilience
- Need single-file HTML prototype (no build step, instant deploy)
- Backend is FastAPI/Python with JSON file persistence

## What's Included

| File | Purpose |
|------|---------|
| `DESIGN.md` | Apple dashboard design system (colors, typography, components, layout, dos-donts) |
| `assets/template.html` | Minimal three-column dashboard skeleton with working task pipeline |
| `references/patterns.md` | 15+ verified design patterns (CSS, JS, API, architecture) |
| `references/anti-patterns.md` | 12 catalogued bugs with root causes and fixes |
| `references/layout.md` | Complete three-column layout CSS and HTML skeleton |

## Quick Start

```bash
cp assets/template.html index.html
python3 -m http.server 3000
# Open http://localhost:3000
```

## Core Design Principles

1. **CSS variables for EVERY color** — never hardcode hex values
2. **`data-mode` for theming** — single attribute toggle for light/dark
3. **Event delegation** — `document.addEventListener` + `closest()` for dynamic content
4. **Inline IIFE onclick** — `onclick="(function(){...})()"` most reliable across environments
5. **File-backed persistence** — JSON files over SQL for internal tools

## Architecture

```
Single HTML file:
  <style>  — CSS variables + component styles + dark mode overrides
  <body>   — Three-column layout: sidebar | content | diagnostics
  <script> — IIFE wrap, XHR data loading, event delegation

API (FastAPI, port 8123):
  GET/PUT  — REST endpoints returning real data from psutil + JSON files
  POST     — Chat messages with LLM context injection
```

## Anti-Patterns to Avoid

1. ❌ `addEventListener` + `onclick` on same element → double-fires
2. ❌ `{overflow:hidden}` on parent when child needs scroll
3. ❌ `random.uniform()` for metrics → always use real data or `null`
4. ❌ ISO date strings treated as timestamps → use `_parse_ts()`
5. ❌ `var tasks` in XHR callback used in sibling callback → declare at parent scope
6. ❌ `python3 executor.py` subprocess → use `athena_ai_plan_runner.py` with CLI entry point

See `references/anti-patterns.md` for full catalog with root causes.

## Design Token Reference

See `DESIGN.md` for the complete 9-section design system compatible with Open Design's schema.

## Open Design Integration

This skill's `DESIGN.md` is portably compatible with Open Design (nexu-io/open-design). If Open Design is available, load `DESIGN.md` as the active design system:

```bash
# Open Design is installed at /tmp/open-design, running on port 60479
# Start:  bin/start-open-design.sh
# Stop:   bin/stop-open-design.sh
# Web UI: http://127.0.0.1:60479/

# In Open Design web UI: Settings → Design System → Import → paste DESIGN.md
# Or programmatically:
open http://127.0.0.1:60479/?design=athena-dashboard
```
