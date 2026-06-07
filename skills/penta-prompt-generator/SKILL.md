---
name: penta-prompt-generator
version: "1.0.0"
description: "PENTA 提示词自动生成 — 将中文分镜脚本转换为 HappyHorse I2V 标准英文提示词"
autoApply: false
dependencies:
  - happyhorse-prompt-library
  - dashscope-platform
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "生成PENTA提示词"
  - "penta prompt"
  - "convert to penta"
  - "自动提示词"
  - "生成英文提示词"
input_schema:
  type: object
  properties:
    scenes:
      type: array
      items:
        type: object
      description: "chinese-drama-script 输出的分镜 JSON 数组"
    character_anchor:
      type: string
      description: "角色锚定描述（可选，默认使用 CHARACTER_ANCHOR）"
    negative_prompt:
      type: string
      description: "负向提示词（可选）"
output_schema:
  type: array
  items:
    type: object
    properties:
      scene_id:
        type: string
      penta_prompt:
        type: string
      penta_score:
        type: integer
      validation:
        type: object
sla:
  target_success_rate: 0.95
  max_latency_ms: 5000
changelog:
  - version: "1.0.0"
    date: "2026-05-07"
      changes: "Initial version — PENTA 提示词自动生成"
---

# Skill: penta-prompt-generator

## Overview
将中文分镜脚本自动转换为 HappyHorse I2V 标准英文 PENTA 提示词，内置五层校验机制。

## When to Use
已有中文分镜脚本（JSON 格式），需要生成 I2V 可用的英文提示词时使用。

## PENTA 五层架构

| 层级 | 名称 | 功能 | 权重 | 必检关键词 |
|------|------|------|------|-----------|
| L1 | 风格锚定 | 锁定视觉风格与格式 | 20% | MCU/9:16/8K/cinematic |
| L2 | 镜头语言 | 定义机位、运镜、构图 | 20% | camera/close-up/wide/angle |
| L3 | 主体刻画 | 角色/场景详细描述 | 25% | CHARACTER_ANCHOR 核心特征 |
| L4 | 光影氛围 | 光照、色彩、粒子、特效 | 20% | volumetric/HDR/lighting |
| L5 | 技术输出 | 分辨率、格式、质量词 | 15% | photorealistic/CGI/Unreal/8K |

## Core Instructions

1. 接收中文分镜 JSON 数组
2. 对每个分镜调用 DashScope API（模型: `deepseek-v3`）生成 PENTA 提示词
3. 执行五层校验，输出评分
4. 返回标准格式数组

### DashScope API 调用格式

```
端点: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
模型: deepseek-v3
认证: Bearer {DASHSCOPE_API_KEY}
```

### System Prompt

```
You are a PENTA prompt engineer for HappyHorse I2V.

Convert the Chinese storyboard scene to an English PENTA prompt following this exact structure:

L1 Style Anchor: "MCU trailer aesthetic, vertical 9:16, 8K ultra-detailed, IMAX quality"
L2 Camera: Translate camera direction to English cinematography terms
L3 Subject: Incorporate CHARACTER_ANCHOR + scene-specific subject details
L4 Lighting: Translate lighting/atmosphere to English cinematic terms
L5 Technical: "photorealistic CGI, Unreal Engine 5, 8K ultra-detailed"

Append standard NEGATIVE_PROMPT at the end.

CHARACTER_ANCHOR: "Athena cyberpunk goddess avatar: European female face, clear cheekbones, sharp jawline, straight nose, natural brown eyebrows, ice-blue iris (#4488EE), dark brown hair swept back, white luminous continuous ring halo above head, obsidian black high-collar tech-armor with neon blue (#00AAFF) and electric orange (#FF8800) circuit patterns, hexagonal glowing core (#00BBFF) at chest center, fiber-optic hair strands with golden particles, realistic human skin texture"

NEGATIVE_PROMPT: "low quality, blurry, deformed, bad anatomy, extra fingers, missing fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, watermark, signature, text, logo, cropped, out of frame, worst quality, low resolution, morbid, mutilated, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, fused fingers, too many fingers, long neck, horizontal composition, landscape orientation, cluttered background, oversaturated, flat lighting, cartoon style, anime style, illustration style"

Rules:
1. Each prompt must contain all 5 PENTA layers in order
2. Output must be entirely in English (no Chinese characters)
3. Maximum 500 characters per prompt
4. Include CHARACTER_ANCHOR key features in L3
5. NEGATIVE_PROMPT must be appended
```

## PENTA 五层校验规则

### 层级检查

| 层级 | 必检关键词（任一命中） | 缺失扣分 |
|------|----------------------|---------|
| L1 风格 | `MCU` / `trailer` / `cinematic` / `9:16` / `vertical` | -2 |
| L2 镜头 | `camera` / `shot` / `angle` / `close-up` / `wide` | -2 |
| L3 主体 | `Athena` / `cyberpunk` / `goddess` / `armor` / `circuit` | -3 |
| L4 光影 | `lighting` / `volumetric` / `HDR` / `glow` / `rim` | -1 |
| L5 技术 | `8K` / `photorealistic` / `CGI` / `Unreal` / `detailed` | -1 |

### 全局校验
- 中文残留：检测任何中文字符（Unicode CJK），每处 -2
- 字符数：> 500 字符 -1
- 负向提示词：未包含 NEGATIVE_PROMPT -2

### 评分公式
```
score = 10 - sum(deductions)
min_score = 0
```

## Output Format

```json
[
  {
    "scene_id": "01",
    "scene_name": "觉醒时刻",
    "penta_prompt": "MCU trailer aesthetic, vertical 9:16, epic cinematic keyframe, 8K. Low-angle heroic shot, symmetrical composition. A majestic cyberpunk Athena goddess as holographic AI avatar... [完整提示词]",
    "penta_score": 10,
    "validation": {
      "L1_style": true,
      "L2_camera": true,
      "L3_subject": true,
      "L4_lighting": true,
      "L5_technical": true,
      "no_chinese": true,
      "under_500_chars": true,
      "has_negative": true,
      "char_count": 423
    }
  }
]
```

## Integration

- 本 Skill 输入对接 `chinese-drama-script` Skill 输出的 `scenes` 数组
- 本 Skill 输出可直接用于 `generate_athena_i2v_v3.py` 的 `build_prompt()` 函数替代
- 复用 `happyhorse-prompt-library` 的 CHARACTER_ANCHOR 和 NEGATIVE_PROMPT

## Testing

1. 输入单分镜 JSON，验证输出包含全部 5 层
2. 输入多分镜 JSON，验证每个分镜独立生成
3. 检查生成的提示词是否无中文残留
4. 检查字符数是否 ≤ 500
5. 验证 CHARACTER_ANCHOR 特征是否包含
