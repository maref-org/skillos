---
name: svg-animator
description: SVG Logo Animator — 矢量路径动画、绘制动效、Icon微交互。输出 .html / .svg / .lottie。独立原子能力，可被社媒Agent、前端Agent、演示Agent独立调用。Use when user asks for "Logo动画", "绘制动效", "SVG动画", "图标动效", "Lottie动画".
---

# SVG Logo Animator

> 矢量路径动画生成器 — 独立原子能力，与 opendesign-skill 平级。
> 通过 Orchestrator 模式联动，不硬编码依赖。

## When to Use

- 需要为 Logo/Icon 生成绘制动画（stroke-dasharray 动画）
- 需要微交互（hover 缩放、弹跳、旋转、颜色渐变）
- 需要导出 Lottie JSON 用于移动端/小程序
- 需要生成 .html 预览文件（开箱即用）
- 独立调用，不依赖设计系统生成流程

## What's Included

| File | Purpose |
|------|---------|
| `SKILL.md` | 本文件 — 能力定义、使用指南 |
| `skill.json` | MCP Tool 注册定义 |
| `executor.py` | ReAct 循环执行引擎 |
| `harness.py` | SVG安全扫描 + 视觉校验层 |
| `tools/iconfont_search.py` | Iconfont 图标搜索 |
| `tools/svg_parser.py` | SVG 路径解析/优化 |
| `tools/lottie_exporter.py` | Lottie JSON 导出 |

## Architecture

```
┌─────────────────────────────────────────┐
│         Creative Suite Workflow         │  ← 可选：上层编排（Meta-Skill）
│    （"给我做一套品牌视觉，含Logo动画"）    │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌──────────────┐    ┌──────────────┐
│  opendesign  │    │ svg-animator │
│    -skill    │    │ (矢量动画)    │
│  (UI/组件)   │    │              │
└──────────────┘    └──────────────┘
    │                     │
    └──────────┬──────────┘
               ▼
        ┌──────────────┐
        │  MCP Gateway  │  ← 统一对外暴露
        │  (A2A协议)    │
        └──────────────┘
```

## Quick Start

```bash
# 基础调用
python3 executor.py --prompt "为品牌设计一个 Logo 绘制动画，配色 #0071e3"

# 带上下文（从 opendesign 传递 VI 结果）
python3 executor.py \
  --prompt "基于以下配色生成Logo绘制动画" \
  --context '{"color_primary": "#0071e3", "color_secondary": "#2f7d4a"}'

# 指定输出格式
python3 executor.py --prompt "..." --format lottie
```

## Output Formats

| Format | Extension | Use Case |
|--------|-----------|----------|
| HTML Preview | `.html` | 浏览器直接预览，开箱即用 |
| Static SVG | `.svg` | 嵌入网页/文档 |
| Lottie JSON | `.json` | 移动端/小程序/React Native |

## Animation Types

| Type | CSS Property | Description |
|------|-------------|-------------|
| Draw | `stroke-dasharray` + `stroke-dashoffset` | 路径绘制效果 |
| Fade | `opacity` | 淡入淡出 |
| Scale | `transform: scale()` | 缩放弹跳 |
| Rotate | `transform: rotate()` | 旋转 |
| Color Shift | `stroke` / `fill` transition | 颜色渐变 |
| Morph | `d` attribute interpolation | 路径变形（需 SMIL） |

## Harness Rules

### Input Filter (SVG Sanitizer)
- 移除 `<script>` 标签
- 移除 `on*` 事件属性
- 移除 `javascript:` URL
- 限制 SVG 尺寸 ≤ 2MB
- 限制动画时长 ≤ 10s

### Output Validation
- SVG 必须包含 `xmlns="http://www.w3.org/2000/svg"`
- 动画必须包含 `@keyframes` 或 `<animate>`
- 颜色值必须为合法 hex/rgb/hsl
- Lottie JSON 必须符合 v5.0+ schema

### Visual Check Loop
1. 生成 SVG → 渲染到无头浏览器
2. 截图 → 与预期对比（可选）
3. 检查动画是否流畅（帧率 ≥ 30fps）
4. 失败 → 重试（max 3 次）

## Context Passing (from opendesign)

```python
# Orchestrator 传递结果摘要，非完整历史
context = {
    "color_primary": "#0071e3",      # 主色
    "color_secondary": "#2f7d4a",    # 辅色
    "font_family": "Inter, sans-serif",
    "brand_name": "BrandName",
    "style": "minimal"               # minimal | geometric | handdrawn
}
```

## Anti-Patterns

1. ❌ 不要硬编码依赖 opendesign — 通过 context 传递参数
2. ❌ 不要共享 Harness 层 — 校验规则完全不同
3. ❌ 不要共享上下文窗口 — 传递结果摘要，避免上下文爆炸
4. ❌ 不要生成 > 2MB 的 SVG — 性能退化
5. ❌ 不要使用 SMIL `<animate>` 用于复杂路径 — 浏览器兼容性差，优先 CSS

## API Integration

```bash
# 通过 Open Design API 生成基础 SVG，再用本 Skill 添加动画
# Step 1: Open Design 生成静态 SVG
curl -s -X POST http://127.0.0.1:60479/api/runs \
  -H "Content-Type: application/json" \
  -d '{"message": "Design a minimalist logo for brand"}'

# Step 2: svg-animator 添加动画
python3 executor.py --input logo.svg --prompt "添加绘制动画，时长2s"
```
