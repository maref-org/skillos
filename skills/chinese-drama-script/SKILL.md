---
name: chinese-drama-script
version: "2.0.0"
description: "中文漫剧脚本生成 — 根据主题自动生成标准分镜脚本 JSON（支持电影感管线v2.0），对接 HappyHorse I2V 管线"
autoApply: false
dependencies:
  - dashscope-platform
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "生成漫剧脚本"
  - "chinese drama script"
  - "中文分镜"
  - "漫剧脚本"
  - "生成中文脚本"
input_schema:
  type: object
  properties:
    topic:
      type: string
      description: "漫剧主题/梗概"
    scene_count:
      type: integer
      description: "分镜数量"
      default: 5
    max_duration:
      type: integer
      description: "总时长上限（秒）"
      default: 60
    style:
      type: string
      description: "风格倾向（轻松/燃向/温情/史诗/神秘）"
      default: "史诗"
    cinematic:
      type: boolean
      description: "启用电影感模式（景别递进+转场设计+声音规划）"
      default: true
output_schema:
  type: object
  properties:
    scenes:
      type: array
      items:
        type: object
        properties:
          id:
            type: string
          action:
            type: string
          camera:
            type: string
          lighting:
            type: string
          dialogue_zh:
            type: string
          dialogue_en:
            type: string
          duration:
            type: integer
          emotion:
            type: string
          shot_type:
            type: string
          angle:
            type: string
          lens:
            type: string
          movement:
            type: string
          transition:
            type: string
sla:
  target_success_rate: 0.95
  max_latency_ms: 5000
changelog:
  - version: "2.0.0"
    date: "2026-05-07"
    changes: "集成电影感管线v2.0：镜头参数化、景别差原则、转场设计、声音架构"
  - version: "1.0.0"
    date: "2026-05-07"
    changes: "Initial version — 中文漫剧脚本生成"
---

# Skill: chinese-drama-script

## Overview
根据主题自动生成标准中文漫剧分镜脚本，输出 JSON 格式直接对接 HappyHorse I2V 管线。

### v2.0 电影感升级

自 v2.0 起，本 Skill 全面集成电影感管线要求：
- 每个镜头必须包含景别、角度、焦段、运镜参数
- 严格执行景别差原则（无连续相同景别）
- 规划转场逻辑（cut/cross_dissolve/fade/match_cut/j_cut/l_cut）
- 声音设计三层架构规划

详细文档:
- 技术报告: `Athena知识库/.../技术文档/电影感管线升级完成报告.md`
- 执行手册: `Athena知识库/.../技术文档/视听语言与制作管线全面升级执行手册.md`
- 核心模块: `scripts/clawra/core/cinematic_shot_script.py`, `storyboard_generator.py`

## When to Use
用户提供漫剧主题、梗概或关键词，需要快速生成分镜脚本时使用。

## Core Instructions

1. 接收用户输入的主题/梗概
2. 调用 DashScope API（模型: `qwen-max`）生成分镜脚本
3. 输出标准化 JSON 格式

### DashScope API 调用格式

```
端点: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
模型: qwen-max
认证: Bearer {DASHSCOPE_API_KEY}
```

### System Prompt

```
你是专业中文短视频分镜导演，擅长漫剧/短视频脚本创作。
掌握电影感镜头语言，严格执行景别差原则。

根据以下要求生成分镜脚本：
- 主题: {topic}
- 分镜数: {scene_count}
- 总时长: ≤ {max_duration}秒
- 风格: {style}
- 电影感模式: {cinematic}

每个分镜必须包含以下字段（JSON 格式）：
{
  "scenes": [
    {
      "id": "01",
      "name": "分镜名称",
      "action": "角色动作/表情描述（中文）",
      "camera": "运镜方式（专业术语）",
      "lighting": "光影氛围描述（中文）",
      "dialogue_zh": "中文台词（口语化）",
      "dialogue_en": "英文翻译",
      "duration": 10,
      "emotion": "情绪标签",
      "shot_type": "ELS/LS/MS/CU/ECU/MACRO",
      "angle": "eye_level/low_angle/high_angle/dutch_angle/over_shoulder",
      "lens": "16mm/24mm/35mm/50mm/85mm/135mm/200mm",
      "movement": "fixed/dolly_in/dolly_out/pan/truck/follow/tilt/crane/handheld/orbit",
      "transition": "cut/cross_dissolve/fade/match_cut/j_cut/l_cut"
    }
  ]
}

规则：
1. 每分镜时长 5-15 秒，总时长不超过 {max_duration} 秒
2. action 描述要具体可执行（含表情、手势、姿态）
3. camera 使用专业运镜术语
4. dialogue_zh 要口语化，适合配音
5. dialogue_en 要忠实原文，适合口型匹配
6. emotion 使用单一情绪词（觉醒/庄严/温情/警觉/邀请/喜悦）
7. 【电影感模式】严禁连续两个镜头使用相同景别（景别差原则）
8. 【电影感模式】每个镜头必须包含 shot_type, angle, lens, movement, transition 参数
9. 【电影感模式】景别递进遵循: ELS→LS→MS→CU→ECU→MACRO 的层次
```

## Output Format

严格按照以下 JSON schema 输出：

```json
{
  "topic": "主题名称",
  "total_duration": 50,
  "scenes": [
    {
      "id": "01",
      "name": "分镜名称",
      "action": "眼睛缓慢眨动一次...",
      "camera": "低角度面部特写，30度仰角",
      "lighting": "深空黑色背景，青橙色调...",
      "dialogue_zh": "我醒了。",
      "dialogue_en": "I have awakened.",
      "duration": 10,
      "emotion": "觉醒",
      "shot_type": "CU",
      "angle": "low_angle",
      "lens": "85mm",
      "movement": "dolly_in",
      "transition": "cross_dissolve"
    }
  ]
}
```

### 电影感参数速查

#### 景别 (Shot Type)
| 缩写 | 中文名 | 用途 |
|:--|:--|:--|
| ELS | 远景 | 建立空间感、气势 |
| LS | 全景 | 展示动作、关系 |
| MS | 中景 | 叙事、对话 |
| CU | 近景 | 情绪表达 |
| ECU | 特写 | 强调情绪、细节 |
| MACRO | 大特写 | 视觉冲击 |

#### 转场 (Transition)
| 类型 | 适用场景 |
|:--|:--|
| cut | 快节奏、动作 |
| cross_dissolve | 时间流逝、回忆 |
| fade | 场景开始/结束 |
| match_cut | 相似动作/形状 |
| j_cut | 声音先入，悬念 |
| l_cut | 声音延续，平滑 |

## Examples

### Success

**Input:**
```
生成漫剧脚本
主题: Athena 觉醒时刻
分镜数: 5
风格: 史诗
```

**Output:**
```json
{
  "topic": "Athena 觉醒时刻",
  "total_duration": 50,
  "scenes": [
    {
      "id": "01",
      "name": "觉醒时刻",
      "action": "eyes slowly blink once, eyelids gently close and open, gaze shifts from upward to直视镜头, lips subtly part",
      "camera": "低角度面部特写，30度仰角",
      "lighting": "深空黑色背景，青橙色调，冷蓝边缘光，暖金补光",
      "dialogue_zh": "我醒了。",
      "dialogue_en": "I have awakened.",
      "duration": 10,
      "emotion": "觉醒",
      "shot_type": "CU",
      "angle": "low_angle",
      "lens": "85mm",
      "movement": "dolly_in",
      "transition": "cross_dissolve"
    }
  ]
}
```

## Integration

- 本 Skill 输出的 `scenes` 数组可直接对接 `generate_athena_i2v_v3.py` 的 `SCENES` 变量
- 与 `penta-prompt-generator` Skill 配合使用实现全自动管线
- 复用 `dashscope-platform` Skill 的 API Key 管理
- 电影感管线对接: `cinematic_shot_script.py`, `storyboard_generator.py`, `cinematic_post_producer.py`

## Testing

1. 输入简单主题，检查是否输出合法 JSON
2. 检查每个分镜是否包含所有必填字段
3. 验证总时长不超过 max_duration
4. 验证 dialogue_zh 口语化程度
5. 验证 dialogue_en 翻译准确度
6. [v2.0] 验证景别递进合理，无连续相同景别
7. [v2.0] 验证每个镜头包含 shot_type, angle, lens, movement, transition
8. [v2.0] 验证景别递进遵循 ELS→LS→MS→CU→ECU→MACRO
