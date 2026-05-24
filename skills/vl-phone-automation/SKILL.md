---
name: vl-phone-automation
description: "VL 视觉语言模型驱动的手机 Agent — Vision Router prompt 工程、OCR 坐标注入、历史感知提示、per-action 循环检测、模型优先级路由。Invoke 当需要优化 VL 模型的手机操作理解能力、调整 Vision Router 配置、手机截图分析、动作生成策略。"
version: "1.0.0"
autoApply: false
dependencies:
  - samsung-oneui-automation
platforms:
  - claude
  - opencode
triggers:
  - "VL 手机自动化"
  - "Vision Router"
  - "视觉路由"
  - "VL prompt"
  - "视觉模型提示词"
  - "手机 Agent 视觉"
  - "OCR 坐标注入"
  - "循环检测阈值"
  - "手机截图分析"
  - "视觉语言模型手机"
input_schema:
  type: object
  properties:
    task:
      type: string
      description: "手机操作任务描述"
    screenshot_path:
      type: string
      description: "截图路径"
    ocr_result:
      type: object
      description: "OCR 结果 (texts + positions)"
sla:
  target_success_rate: 0.80
  max_latency_ms: 10000
changelog:
  - version: "1.0.0"
    date: "2026-05-08"
    changes: "Initial version — Vision Router V2 + prompt engineering + loop detection"
---

# Skill: vl-phone-automation

## Overview

VL (Vision Language) 模型作为手机 Agent 核心引擎的最佳实践。涵盖 Vision Router V2 的完整 pipeline：prompt 工程策略、OCR 上下文传递、历史感知、模型路由、循环检测调优。

在 Z Flip3 (1080×2640) 上通过 qwen-vl-max-latest (百炼) 验证。

---

## VL Prompt 工程

### 核心原则

1. **直出动作 JSON，不要元素定位** — 让 VL 同时决定"做什么"和"在哪里做"
2. **Few-shot 示例必须精确** — 包含真实坐标和动作类型
3. **OCR 坐标必须注入 prompt** — VL 模型凭视觉猜坐标误差大
4. **历史感知提示** — 告知上一步操作，引导下一步

### 标准 Prompt 模板

```
System:
  你是三星 One UI 手机桌面自动化助手。OCR 坐标已标注。
  三星进入编辑模式: 长按App→点"选择"→图标可拖动。
  操作示例:
  - 长按WPS: {"action":"long_press","params":{"x_norm":0.25,"y_norm":0.43}}
  - 拖到Termux: {"action":"swipe","params":{"x1_norm":0.25,"y1_norm":0.43,"x2_norm":0.50,"y2_norm":0.43}}
  - 翻页: {"action":"swipe","params":{"x1_norm":0.8,"y1_norm":0.5,"x2_norm":0.2,"y2_norm":0.5}}
  - 长按→swipe两步=拖放, 不要一直重复同一操作

User:
  任务: 整理手机桌面
  OCR坐标: WPS Office@(270,1135), Termux@(415,1072), ...
  输出JSON动作
```

代码位置: `agent_system/vision/vision_router.py:387-432`

### Few-shot 示例设计规则

| 规则 | 说明 |
|------|------|
| 使用真实坐标 | 示例坐标应接近实际屏幕布局 |
| 覆盖所有动作类型 | tap / long_press / swipe / back / home / input_text |
| 不超过 6 个示例 | 过多示例导致 prompt 过长 |
| 含 `done` 退出示例 | 让模型知道何时可以停止 |

### 历史感知提示

```python
# agent_loop.py — enhanced_task 追加
if history and history[-1].action == "long_press":
    enhanced_task += "\n提示：上一步是长按，下一步应该是swipe滑动来拖动图标。"
```

规则: long_press→swipe, back→home, select_mode→tap_or_swipe

---

## OCR 坐标注入 pipeline

### 数据流

```
screenshot → RapidOCR → ocr_context{texts, positions}
    → route_vision_analysis(ocr_result=ocr_context)
    → _call_openai_vl → ocr_hint = "WPS@(270,1135), Termux@(415,1072)..."
    → VL model prompt with coordinates
```

### 正确格式

```python
# vision_router.py _call_openai_vl
ocr_positions = ocr_result.get("ocr_positions", [])
# ocr_positions already in "TEXT@(x,y)" format from _try_ocr_grounding
items = [op for op in ocr_positions if op and "@" in op]
ocr_hint = f"\nOCR 识别 (文本@坐标): {', '.join(items[:15])}"
```

**常见错误**: 二次包装坐标 → `"WPS@(WPS@(270,1135))"` — 因为 `ocr_positions` 已含完整格式

---

## 循环检测调优

### Per-Action 阈值 (memory.py)

```python
_ACTION_LOOP_THRESHOLDS = {
    "tap": 12,        # 高频操作, 高容忍
    "swipe": 8,       # 翻页/拖动可连续
    "long_press": 8,  # 编辑模式可连续
    "back": 4,        # 连续返回=迷路
    "home": 3,        # 重复回家=无意义
    "input_text": 5,
}
_DEFAULT_LOOP_THRESHOLD = 5
```

### 何时调整阈值

| 场景 | 调整 |
|------|------|
| 桌面整理(大量拖放) | long_press↑, swipe↑ |
| Web 浏览(大量点击) | tap↑↑ |
| 文本编辑 | input_text↑ |

---

## VL 模型优先级路由

```python
VL_MODEL_PRIORITY = [
    ("dashscope", "qwen-vl-max-latest", "百炼Pro VL"),   # 通用强
    ("dashscope", "qwen-max-latest", "百炼Pro Max"),      # 降级
]
```

### 接入新模型

```python
VL_MODEL_PRIORITY.insert(0, 
    ("your_provider_id", "model-id", "Label"))
```

Provider ID 必须匹配 `mini_agent/agent/core/provider_registry` 中的注册名。

---

## 模型推理后备 (DeepSeek)

当 VL/OCR 都无结果时, 回退到 DeepSeek 文本推理:

```python
# agent_loop.py — model inference fallback
enhanced_task = f"{task}\n\n当前屏幕可见元素(带坐标): {pos_info}"
model_output = self.model_client.infer_action(
    task=enhanced_task,
    screenshot_path=screenshot_path,
    history=history[-3:],
    use_mock=False,
)
```

System prompt 允许所有动作类型: tap/swipe/input_text/back/home/long_press

---

## 测试清单

- [ ] VL 模型输出 4 种动作类型 (tap/long_press/swipe/home)
- [ ] OCR 坐标出现在 VL prompt 中
- [ ] 连续 8 次 long_press 不被误判为循环
- [ ] 历史感知: long_press 后下一触发为 swipe
- [ ] 模型路由: 百炼失败 → 自动降级

## Changelog

See frontmatter.
