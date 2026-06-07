---
name: animagine-prompt-enhancer
version: "2.0.0"
description: "Animagine 提示词增强器 — 基于 CSV 角色库 + 质量标签 + 动态通配符的 PENTA 提示词工程系统"
autoApply: false
dependencies:
  - happyhorse-prompt-library
  - dashscope-platform
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "增强提示词"
  - "animagine prompt"
  - "csv角色提示词"
  - "批量提示词"
  - "质量标签提示词"
  - "prompt enhancer"
input_schema:
  type: object
  properties:
    scenes:
      type: array
      items:
        type: object
      description: "llm-script-factory 输出的分镜 JSON 数组"
    character_csv:
      type: string
      description: "CSV 角色库路径（可选）"
    quality_level:
      type: string
      description: "质量等级（masterpiece/best/high quality）"
      default: "masterpiece"
    style_preset:
      type: string
      description: "风格预设（anime/realistic/cinematic/cyberpunk）"
      default: "cinematic"
    negative_prompt:
      type: string
      description: "负向提示词（可选，使用默认）"
    max_chars:
      type: integer
      description: "最大字符数限制"
      default: 500
output_schema:
  type: array
  items:
    type: object
    properties:
      scene_id:
        type: string
      scene_name:
        type: string
      penta_prompt:
        type: string
      penta_score:
        type: integer
      character_used:
        type: string
      quality_tags:
        type: array
      validation:
        type: object
sla:
  target_success_rate: 0.95
  max_latency_ms: 30000
changelog:
  - version: "2.0.0"
    date: "2026-05-07"
    changes: "集成 CSV 角色库、质量标签系统、动态通配符、PENTA 五层校验"
  - version: "1.0.0"
    date: "2026-05-07"
    changes: "Initial version — 基础提示词增强"
---

# Skill: animagine-prompt-enhancer

## Overview

基于 Animagine-Prompt 架构的提示词增强系统，集成：
1. **CSV 角色库**：预存角色属性，批量调用保持一致性
2. **质量标签系统**：自动注入 Quality/Score/Rating 标签
3. **动态通配符**：支持变量替换和条件生成
4. **PENTA 五层校验**：确保提示词符合 HappyHorse I2V 标准

## CSV 角色库格式

```csv
GENDER,CHARACTER,COPYRIGHT,DESCRIPTION,EMOTION_ARC,STYLE_TAGS
1girl,Athena,Cyberpunk Goddess,"European female face, clear cheekbones, sharp jawline, straight nose, natural brown eyebrows, ice-blue iris (#4488EE), dark brown hair swept back, white luminous continuous ring halo above head, obsidian black high-collar tech-armor with neon blue (#00AAFF) and electric orange (#FF8800) circuit patterns, hexagonal glowing core (#00BBFF) at chest center, fiber-optic hair strands with golden particles, realistic human skin texture with visible pores, natural subsurface scattering, warm undertone, subtle skin imperfections",沉睡→觉醒→庄严→警觉→邀请,"cyberpunk,goddess,armor,glowing,halo"
1boy,Mentor,Wise Guide,"Old man with white beard, deep wrinkles, warm brown eyes, weathered face, silver hair, sage robes with gold trim, wooden staff with crystal orb",平静→严肃→欣慰→智慧,"fantasy,mentor,wise,old,robes"
```

### 字段说明

| 字段 | 用途 | 示例 |
|------|------|------|
| GENDER | 1girl/1boy/2girls/2boys | 1girl |
| CHARACTER | 角色名称 | Athena |
| COPYRIGHT | 角色所属世界观 | Cyberpunk Goddess |
| DESCRIPTION | 外貌详细描述（注入 L3） | European female face... |
| EMOTION_ARC | 情绪弧线 | 觉醒→庄严→警觉 |
| STYLE_TAGS | 风格标签（CSV 注入） | cyberpunk,goddess,armor |

## 质量标签系统

### 质量等级

| 等级 | 标签 | 用途 |
|------|------|------|
| 最高 | `masterpiece, best quality, ultra-detailed, 8K` | 主角特写/关键帧 |
| 高 | `high quality, very detailed, 4K` | 中景/动作场景 |
| 中 | `good quality, detailed, HD` | 远景/过渡场景 |

### 评分标签

| 标签 | 分值 | 用途 |
|------|------|------|
| `rating:explicit` | 成人内容 | 不适用 |
| `rating:questionable` | 敏感内容 | 不适用 |
| `rating:safe` | 安全内容 | 默认使用 |
| `score:9` | 最高质量 | 关键帧使用 |
| `score:8` | 高质量 | 常规使用 |

### 年份标签

| 标签 | 风格倾向 |
|------|----------|
| `2024` | 最新 AI 绘画风格 |
| `2023` | 稳定主流风格 |

## 动态通配符语法

### 基础语法

```
{{character_name}} → 从 CSV 替换为角色名
{{description}} → 从 CSV 替换为外貌描述
{{emotion}} → 替换为当前分镜情绪
{{camera}} → 替换为运镜描述
{{lighting}} → 替换为光影描述
```

### 条件通配符

```
{{#if emotion:觉醒}}glowing eyes, energy aura{{/if}}
{{#if camera:特写}}detailed facial expression, visible pores{{/if}}
```

### 循环通配符

```
{{#each style_tags}}
{{this}},
{{/each}}
→ cyberpunk, goddess, armor, glowing, halo,
```

## PENTA 提示词生成流程

### 步骤 1: 读取 CSV 角色库

```python
import csv

def load_character_csv(csv_path: str) -> dict:
    characters = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            characters[row['CHARACTER']] = row
    return characters
```

### 步骤 2: 匹配分镜角色

```python
def match_character(scene: dict, characters: dict) -> dict:
    focus = scene.get('character_focus', 'Athena')
    return characters.get(focus, characters.get('Athena', {}))
```

### 步骤 3: 构建 PENTA 提示词

```
L1 风格锚定: "{quality_level}, {style_preset}, vertical 9:16, 8K ultra-detailed, IMAX quality, rating:safe, score:9"

L2 镜头语言: "{camera_english}, professional cinematography, dramatic composition"

L3 主体刻画: "{character_description}, {action_english}, {emotion_visualized}"

L4 光影氛围: "{lighting_english}, cinematic lighting, volumetric atmosphere"

L5 技术输出: "photorealistic CGI, Unreal Engine 5, 8K ultra-detailed, masterpiece"

NEGATIVE: "{negative_prompt}"
```

### 步骤 4: 质量校验

| 校验项 | 检查内容 | 失败处理 |
|--------|----------|----------|
| CSV 注入 | 角色描述是否完整注入 | 重新匹配 |
| 长度检查 | ≤ max_chars 字符 | 截断 L4/L5 |
| 中文检测 | 无中文字符 | 翻译为英文 |
| PENTA 五层 | 全部层级存在 | 补全缺失层 |
| 负向提示词 | 包含负面关键词 | 自动追加 |

## Core Instructions

### 调用格式

```
端点: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
模型: deepseek-v3
认证: Bearer {DASHSCOPE_API_KEY}
```

### System Prompt

```
You are an Animagine prompt engineer specializing in PENTA prompt generation with CSV character library integration.

Your task is to convert Chinese storyboard scenes into English PENTA prompts following this exact structure:

L1 Style Anchor: "{quality_level}, {style_preset}, vertical 9:16, 8K ultra-detailed, IMAX quality, rating:safe, score:9, 2024"

L2 Camera: Translate {camera} to English cinematography terms (shot type, angle, movement, composition)

L3 Subject: Inject character description from CSV + translate {action} to English + visualize {emotion}

L4 Lighting: Translate {lighting} to English cinematic lighting terms (volumetric, HDR, glow, rim light, etc.)

L5 Technical: "photorealistic CGI, Unreal Engine 5, 8K ultra-detailed, masterpiece"

NEGATIVE_PROMPT: "low quality, blurry, deformed, bad anatomy, extra fingers, missing fingers, mutated hands, poorly drawn hands, poorly drawn face, mutation, watermark, signature, text, logo, cropped, out of frame, worst quality, low resolution, morbid, mutilated, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, fused fingers, too many fingers, long neck, horizontal composition, landscape orientation, cluttered background, oversaturated, flat lighting, cartoon style, anime style, illustration style"

Rules:
1. Each prompt must contain all 5 PENTA layers in order, separated by newlines
2. Entirely in English (no Chinese characters)
3. Maximum {max_chars} characters per prompt
4. Include CHARACTER_ANCHOR key features in L3
5. NEGATIVE_PROMPT must be appended at the end
6. Quality tags from quality_level must be in L1
7. Output JSON array only, no markdown

CSV Character Library:
{csv_content}

For each scene, match the character_focus to CSV entry and inject description.
```

## Output Format

```json
[
  {
    "scene_id": "01",
    "scene_name": "觉醒时刻",
    "penta_prompt": "masterpiece, cinematic, vertical 9:16, 8K ultra-detailed, IMAX quality, rating:safe, score:9, 2024\nLow-angle close-up shot, symmetrical composition, slow push-in\nAthena cyberpunk goddess avatar: European female face, clear cheekbones, ice-blue iris (#4488EE), obsidian black high-collar tech-armor with neon blue circuit patterns, white luminous continuous ring halo above head, eyes slowly open, subtle lip part,觉醒 energy visualized as golden aura\nDeep space black background, cool blue rim light, warm gold fill, volumetric haze\nphotorealistic CGI, Unreal Engine 5, 8K ultra-detailed, masterpiece, low quality, blurry, deformed, bad anatomy...",
    "penta_score": 10,
    "character_used": "Athena",
    "quality_tags": ["masterpiece", "best quality", "8K", "rating:safe", "score:9"],
    "validation": {
      "L1_style": true,
      "L2_camera": true,
      "L3_subject": true,
      "L4_lighting": true,
      "L5_technical": true,
      "no_chinese": true,
      "under_500_chars": true,
      "has_negative": true,
      "char_count": 485,
      "csv_injected": true
    }
  }
]
```

## Integration

- 输入对接 `llm-script-factory` Skill 输出的 scenes 数组
- 可选读取 CSV 角色库实现角色一致性
- 输出对接 HappyHorse I2V 或 ComfyUI T2I 管线
- 复用 `happyhorse-prompt-library` 的 CHARACTER_ANCHOR 和 NEGATIVE_PROMPT

## Testing

1. 输入单分镜 JSON，验证输出包含全部 5 层
2. 输入 CSV 路径，验证角色描述正确注入
3. 检查生成的提示词是否无中文残留
4. 检查字符数是否 ≤ max_chars
5. 验证质量标签是否正确注入 L1
6. 验证 NEGATIVE_PROMPT 是否追加
