# Apple Dashboard Design System
> Category: Developer Tools / Operations

## 1. Visual Theme & Atmosphere

- Clean, minimal, information-forward with generous white space
- Three-column layout optimized for data-dense agent operations
- Subtle depth via 1-2px shadows and subtle border separators
- Frosted-glass topbar (backdrop-filter: blur)
- No purple gradients, no rounded-card-with-left-border-accent

## 2. Color Palette & Roles

### Light Mode (`:root`)
```
  --accent:#0071e3;--accent-hover:#0066cc;--ink:#1d1d1f;--bg:#f5f5f7;
  --surface:#ffffff;--muted:#6e6e73;--border-soft:#d2d2d7;--border-mid:#86868b;
  --good:#2f7d4a;--warn:#b85c00;--danger:#b53a2a;
```

| Token | Hex | Role |
|-------|-----|------|
| --accent | #0071e3 | Primary buttons, active states, links |
| --accent-hover | #0066cc | Button hover |
| --ink | #1d1d1f | Primary text |
| --bg | #f5f5f7 | Page background |
| --surface | #ffffff | Cards, panels, sidebars |
| --muted | #6e6e73 | Secondary text, labels |
| --border-soft | #d2d2d7 | Card borders, separators |
| --border-mid | #86868b | Stronger borders |
| --good | #2f7d4a | Success, completed, healthy |
| --warn | #b85c00 | Warning, caution |
| --danger | #b53a2a | Errors, failures, alerts |

### Dark Mode (`[data-mode="dark"]`)
```
  --accent:#0a84ff;--accent-hover:#409cff;--ink:#f0f0f2;--bg:#1d1d1f;
  --surface:#2c2c2e;--muted:#a8a8ad;--border-soft:#48484a;--border-mid:#727275;
  --good:#30d158;--warn:#ff9f0a;--danger:#ff453a;
```

### Dark Mode Specific Overrides
```css
[data-mode="dark"] .sidebar-nav a{color:#ffffff;font-weight:500}
[data-mode="dark"] .sidebar-nav a:hover{background:rgba(255,255,255,0.08)}
[data-mode="dark"] .sidebar-nav a.active{background:var(--accent);color:#ffffff}
[data-mode="dark"] .sidebar-nav a .badge{background:#48484a;color:#e0e0e2}
[data-mode="dark"] .sidebar-brand{color:#ffffff}
[data-mode="dark"] .sidebar-footer{color:#a8a8ad;border-top-color:#48484a}
[data-mode="dark"] .topbar{background:rgba(44,44,46,0.92)}
[data-mode="dark"] .msg-ai .body{color:#e0e0e2}
[data-mode="dark"] .kpi-card .val{color:#ffffff}
[data-mode="dark"] .panel h3{color:#ffffff}
[data-mode="dark"] table td{color:#e0e0e2}
[data-mode="dark"] table th{color:#a8a8ad}
```

## 3. Typography Rules

- **Font**: `-apple-system, 'Inter', 'SF Pro Text', system-ui, sans-serif`
- **Mono**: `'SF Mono', 'JetBrains Mono', monospace`
- **Body**: 14px / 1.5 line-height
- **Nav items**: 13px, font-weight 500
- **Section labels**: 10px, uppercase, 0.08em tracking
- **KPI values**: 28px, font-weight 700, -0.02em tracking
- **Metrics**: 11px, 'SF Mono'
- **Headings**: 13-16px, font-weight 600

## 4. Component Stylings

### Toggle Switch
```css
.tog{width:40px;height:20px;border-radius:10px;cursor:pointer;border:none}
.tog.on{background:var(--accent)}
.tog.off{background:var(--bg);border:1px solid var(--border-soft)}
.tog::after{content:'';width:14px;height:14px;border-radius:50%;background:white;transition:transform 0.2s}
.tog.on::after{transform:translateX(20px)}
```

### Badge / Pill
```css
.pill{font-size:10px;font-weight:600;padding:2px 8px;border-radius:99px}
.pill.success{color:var(--good)}
.pill.danger{color:var(--danger)}
.pill.running{color:var(--accent)}
```

### KPI Card
```css
.kpi-card{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-lg);padding:16px 18px}
.kpi-card .lbl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em}
.kpi-card .val{font-size:28px;font-weight:700}
```

### Chat Message (AI)
```css
.msg-ai{background:var(--surface);border:1px solid var(--border-soft);border-radius:var(--radius-lg);padding:24px}
.msg-ai .ai-header{display:flex;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border-soft)}
.msg-ai .ai-header .dot{width:16px;height:16px;border-radius:50%;background:var(--accent)}
```

### Progress Bar
```css
.meter{height:3px;border-radius:2px;background:var(--bg);overflow:hidden}
.meter .f{height:100%;border-radius:2px;transition:width 1s ease}
.meter .f.blue{background:var(--accent)}
```

## 5. Layout Principles

### Three-Column Grid
```
#sidebar-left (240px min200 max360) | #center-col (flex:1) | #sidebar-right (300px min240 max400)
```
- Left sidebar: navigation + conversation list, collapsible to 0
- Center column: views (chat/dashboard/agents/skills/monitoring/settings)
- Right sidebar: diagnostics, event log, task queue, collapsible to 0
- Resize handles (4px wide, col-resize cursor) between columns
- Collapse buttons (18×48px, rounded right edge) on sidebar edges

### Topbar
```css
.topbar{height:var(--top-h);background:rgba(255,255,255,0.85);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--border-soft)}
```

### Scroll Areas (each view has its own)
```css
.chat-scroll,.dash-scroll,.ag-scroll,.sk-scroll,.st-scroll,.mo-scroll,.cd-scroll
{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}
```

### View Switching
```css
.v{display:none;flex-direction:column;flex:1;min-height:0}
.v.active{display:flex}
```

## 6. Depth & Elevation

- **sm shadow**: `0 1px 2px rgba(0,0,0,0.04)`
- **md shadow**: `0 2px 10px rgba(0,0,0,0.04)`
- **Border**: `1px solid var(--border-soft)` on cards/panels
- No heavy shadows (Apple-style minimal elevation)

## 7. Do's and Don'ts

| Do | Don't |
|----|-------|
| Use CSS custom properties for all colors | Hardcode color values in component CSS |
| Use `data-mode` for theme switching | Use class-based theming |
| Use `overflow-y:auto` on each view container | Set overflow on parent view container |
| Use `flex-wrap:wrap` for zoom resilience | Use fixed widths without flex wrapping |
| Use event delegation (document.addEventListener) for dynamic content | Use inline onclick relying on IIFE-scoped functions |
| Use `closest()` for event target matching | Use `e.target` directly for nested elements |
| Set `min-height:0` on flex children that scroll | Rely on implicit flex sizing for scroll containers |

## 8. Responsive Behavior

- Three-column layout with **flex:1** on center column
- Sidebars have **min-width** and **max-width** constraints
- **flex-wrap:wrap** on profile cards, settings rows
- Inputs use `flex:1` with `min-width` fallbacks
- **150% zoom** tested: content wraps, scrollbars visible on overflow
- Collapse buttons hide sidebars at mobile sizes
- `scrollbar-width:auto` on settings scroll for forced visibility

## 9. Agent Prompt Guide

When building a dashboard or agent console with this design system:

```
Use the CSS custom properties defined above for ALL colors.
Never hardcode #hex values in component code.
Use <div class="v" id="v-{name}"> for each view.
Each view needs its own scroll container (class="{name}-scroll").
Use sidebar-nav <a data-view="{name}"> links for navigation.
All data fetching uses XMLHttpRequest to localhost:{port}/api/v1/{endpoint}.
Refresh data with setInterval.
Handle errors with console.error and visible error messages in chat.
Time-filter old data (Date.now() - 86400000 * days).
```
