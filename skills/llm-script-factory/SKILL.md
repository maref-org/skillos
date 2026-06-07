---
name: llm-script-factory
version: "2.0.0"
description: "专业短剧/漫剧剧本工厂 — 6阶段工作流（创意→结构→分场→剧本→润色→剧本医生），输出标准化 JSON 对接 I2V 管线"
autoApply: false
dependencies:
  - dashscope-platform
platforms:
  - claude
  - opencode
  - trae
triggers:
  - "生成漫剧剧本"
  - "llm script factory"
  - "专业剧本"
  - "6阶段剧本"
  - "script factory"
input_schema:
  type: object
  properties:
    topic:
      type: string
      description: "漫剧主题/核心创意/一句话梗概（logline）"
    episode_count:
      type: integer
      description: "集数（短剧模式）"
      default: 1
    scene_count:
      type: integer
      description: "每集分镜数"
      default: 5
    max_duration:
      type: integer
      description: "总时长上限（秒）"
      default: 60
    style:
      type: string
      description: "风格倾向（轻松/燃向/温情/史诗/神秘/悬疑/喜剧）"
      default: "史诗"
    character_csv:
      type: string
      description: "CSV 角色库路径（可选，默认使用内置 CHARACTER_ANCHOR）"
    enable_polish:
      type: boolean
      description: "启用剧本医生润色阶段"
      default: true
output_schema:
  type: object
  properties:
    metadata:
      type: object
      properties:
        topic:
          type: string
        genre:
          type: string
        total_duration:
          type: integer
        episode_count:
          type: integer
    characters:
      type: array
      items:
        type: object
        properties:
          name:
            type: string
          role:
            type: string
          description:
            type: string
          emotion_arc:
            type: string
    scenes:
      type: array
      items:
        type: object
        properties:
          id:
            type: string
          name:
            type: string
          beat:
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
          character_focus:
            type: string
sla:
  target_success_rate: 0.95
  max_latency_ms: 45000
changelog:
  - version: "3.0.0"
    date: "2026-05-07"
    changes: "集成电影感管线v2.0：镜头脚本格式（景别/角度/焦段/运镜/转场）、景别差原则、情绪曲线、三层声音架构"
  - version: "2.0.0"
    date: "2026-05-07"
    changes: "升级至 6 阶段工作流：创意孵化→结构构建→分场编写→剧本撰写→润色优化→剧本医生，支持 CSV 角色库"
  - version: "1.0.0"
    date: "2026-05-07"
    changes: "Initial version — 基础分镜脚本生成"
---

# Skill: llm-script-factory

## Overview

专业短剧/漫剧剧本工厂，采用 6 阶段工作流从一句话创意生成完整分镜脚本：

| 阶段 | 名称 | 模型 | 功能 | 输出 |
|------|------|------|------|------|
| 1 | 创意孵化 | qwen-max | 扩展 logline 为完整故事概念 | 故事大纲、主题、冲突 |
| 2 | 结构构建 | qwen-max | 设计三幕剧/英雄之旅结构 | 情节节点、转折点 |
| 3 | 分场编写 | qwen-max | 将结构拆分为具体分镜 | 分镜列表、时长分配 |
| 4 | 剧本撰写 | qwen-max | 填充台词、动作、运镜 | 完整分镜脚本 JSON |
| 5 | 润色优化 | deepseek-v3 | 优化台词口语化、动作可执行性 | 优化后脚本 |
| 6 | 剧本医生 | deepseek-v3 | 质量检查、逻辑一致性验证 | 最终脚本+质量报告 |

### v3.0 电影感升级

自 v3.0 起，本 Skill 全面集成《视听语言与制作管线全面升级执行手册》的四个模块要求：
- **模块一**: 镜头脚本格式（景别/角度/焦段/运镜/转场参数）
- **模块二**: 景别递进表与转场逻辑设计
- **模块三**: 声音设计三层架构（环境音/音效/情绪音乐）
- **模块四**: 执行工作流与交付标准

详细文档:
- 技术文档: `Athena知识库/.../技术文档/电影感管线升级完成报告.md`
- 执行手册: `Athena知识库/.../技术文档/视听语言与制作管线全面升级执行手册.md`
- 核心模块: `scripts/clawra/core/cinematic_shot_script.py`, `storyboard_generator.py`, `sound_designer.py`, `cinematic_post_producer.py`

## When to Use

用户提供一句话创意/主题，需要专业级剧本而非简单分镜时使用。

## Core Instructions

### 阶段 1: 创意孵化 (Creative Incubation)

```
System: 你是专业短剧创意总监，擅长将一句话扩展为完整故事概念。

Input: 用户提供的 logline/主题

Output JSON:
{
  "topic": "扩展后的主题名称",
  "genre": "类型标签",
  "logline": "一句话梗概",
  "theme": "核心主题",
  "conflict": "核心冲突",
  "hook": "吸引观众的钩子"
}
```

### 阶段 2: 结构构建 (Structure Building)

```
System: 你是专业编剧，擅长三幕剧结构和英雄之旅叙事。

Input: 阶段 1 的故事概念

Output JSON:
{
  "acts": [
    {
      "act_number": 1,
      "name": "建置",
      "beats": ["开场画面", "主题呈现", "铺垫"]
    }
  ],
  "plot_points": [
    {"type": "inciting_incident", "description": "激励事件"},
    {"type": "midpoint", "description": "中点转折"},
    {"type": "climax", "description": "高潮"}
  ]
}
```

### 阶段 3: 分场编写 (Scene Breakdown)

```
System: 你是分镜导演，擅长将叙事结构拆分为具体分镜。

Input: 阶段 2 的结构 + 分镜数量要求

Output JSON:
{
  "scenes": [
    {
      "id": "01",
      "act": 1,
      "beat": "开场画面",
      "name": "分镜名称",
      "purpose": "叙事功能",
      "duration": 10
    }
  ]
}
```

### 阶段 4: 剧本撰写 (Script Writing)

```
System: 你是专业编剧，擅长写短视频/漫剧台词和动作描述。

Input: 阶段 3 的分镜列表 + 角色信息

Output JSON:
{
  "metadata": {
    "topic": "主题",
    "genre": "类型",
    "total_duration": 总时长,
    "episode_count": 集数
  },
  "characters": [
    {
      "name": "角色名",
      "role": "主角/配角/反派",
      "description": "外貌/性格描述",
      "emotion_arc": "情绪弧线"
    }
  ],
  "scenes": [
    {
      "id": "01",
      "name": "分镜名称",
      "beat": "情节点",
      "action": "角色动作/表情描述（具体可执行，包含姿态、表情、手势）",
      "camera": "运镜方式（专业术语）",
      "lighting": "光影氛围描述",
      "dialogue_zh": "中文台词（口语化，适合配音）",
      "dialogue_en": "English translation（适合口型匹配）",
      "duration": 10,
      "emotion": "情绪标签",
      "character_focus": "主要角色"
    }
  ]
}
```

### 阶段 5: 润色优化 (Polish & Optimize)

```
System: 你是剧本润色专家，擅长优化台词和动作描述。

Input: 阶段 4 的完整脚本

Tasks:
1. 优化 dialogue_zh 口语化程度
2. 优化 dialogue_en 翻译准确度
3. 确保 action 描述具体可执行
4. 检查情绪弧线连贯性
5. 验证总时长符合要求

Output: 优化后的完整脚本 JSON
```

### 阶段 6: 剧本医生 (Script Doctor)

```
System: 你是剧本医生，擅长质量检查和逻辑验证。

Input: 阶段 5 的脚本

Checks:
1. 逻辑一致性（角色行为是否合理）
2. 时长合理性（每分镜 5-15 秒，总时长不超上限）
3. 台词质量（口语化、无生硬翻译腔）
4. 动作可执行性（I2V 能否生成）
5. 情绪连贯性（情绪弧线是否完整）

Output: 最终脚本 JSON + 质量报告
{
  "script": {...},
  "quality_report": {
    "score": 85,
    "issues": [],
    "suggestions": []
  }
}
```

## CSV 角色库集成

如果提供 `character_csv` 路径，从 CSV 读取角色信息：

```csv
GENDER,CHARACTER,COPYRIGHT,DESCRIPTION,EMOTION_ARC
1girl,Athena,Cyberpunk Goddess,European female face, clear cheekbones, sharp jawline, ice-blue iris,觉醒→庄严→警觉
1boy,Mentor,Wise Guide,Old man with white beard, deep wrinkles, warm eyes,平静→严肃→欣慰
```

角色信息自动注入到阶段 4 的剧本撰写中。

## Output Format

最终输出为标准 JSON，包含 metadata、characters、scenes 三个顶级字段。

scenes 数组中每个分镜必须包含：
- `id`: 分镜编号（字符串，如 "01"）
- `name`: 分镜名称
- `beat`: 对应的情节点
- `action`: 具体可执行的动作描述
- `camera`: 专业运镜术语（见下方电影感镜头参数规范）
- `lighting`: 光影氛围
- `dialogue_zh`: 中文台词
- `dialogue_en`: 英文翻译
- `duration`: 时长（秒）
- `emotion`: 单一情绪词

### 电影感镜头参数规范（v3.0）

每个镜头必须包含以下电影感参数：

#### 景别 (Shot Type)
| 缩写 | 中文名 | 英文 | 用途 | 画面占比 |
|:--|:--|:--|:--|:--|
| ELS | 远景 | Extreme Long Shot | 建立空间感、气势 | 人物<20% |
| LS | 全景 | Long Shot | 展示动作、关系 | 人物全身 |
| MS | 中景 | Medium Shot | 叙事、对话 | 人物腰部以上 |
| CU | 近景 | Close Up | 情绪表达 | 人物胸部以上 |
| ECU | 特写 | Extreme Close Up | 强调情绪、细节 | 面部/手部 |
| MACRO | 大特写 | Macro Shot | 视觉冲击 | 眼睛/嘴唇 |

#### 角度 (Angle)
- `eye_level`: 平视（中性、客观）
- `low_angle`: 仰视（力量、威严）
- `high_angle`: 俯视（脆弱、渺小）
- `dutch_angle`: 倾斜（不安、紧张）
- `over_shoulder`: 过肩（对话、关系）

#### 焦段 (Lens)
- `16mm`: 超广角（夸张透视）
- `24mm`: 广角（空间感）
- `35mm`: 人文（自然视角）
- `50mm`: 标准（人眼视角）
- `85mm`: 中长焦（人像）
- `135mm`: 长焦（压缩感）
- `200mm`: 超长焦（极致压缩）

#### 运镜 (Movement)
- `fixed`: 固定（稳定、客观）
- `dolly_in`: 推入（聚焦、紧张）
- `dolly_out`: 拉出（释放、孤独）
- `pan_left/right`: 左右摇（跟随）
- `truck_left/right`: 左右移（平行）
- `follow`: 跟拍（代入感）
- `tilt_up/down`: 上/下摇（揭示）
- `crane_up/down`: 升/降（气势）
- `handheld`: 手持（真实感）
- `orbit`: 环绕（立体感）

#### 转场 (Transition)
- `cut`: 硬切（快节奏、动作）
- `cross_dissolve`: 交叉溶解（时间流逝、回忆）
- `fade_in/out`: 淡入/出（仪式感）
- `match_cut`: 匹配剪辑（相似动作/形状）
- `j_cut`: 声音先入（悬念、期待）
- `l_cut`: 声音延续（平滑、连贯）

### 景别差原则（v3.0 强制执行）

严禁连续两个镜头使用相同的景别（除非为了特殊 stylistic 目的）。
正确的景别递进：ELS → LS → MS → CU → ECU → MACRO
每个场景应使用不同的镜头模式，确保场景间景别差异。

### 情绪曲线规范（v3.0）

| 情绪值 | 情绪状态 | 音乐音量 | 镜头长度 |
|:--|:--|:--|:--|
| 1-2 | 平静、沉睡 | -20dB | 5-10s |
| 3-4 | 觉醒、好奇 | -15dB | 3-5s |
| 5-6 | 紧张、探索 | -10dB | 2-3s |
| 7-8 | 高潮、冲突 | -5dB | 1-2s |
| 9-10 | 爆发、震撼 | 0dB | 0.5-1s |

### 声音设计三层架构（v3.0）

- **底层**: 环境音（-20dB ~ -30dB）- 建立空间感
- **中层**: 音效（-10dB ~ -20dB）- 增强真实感
- **顶层**: 情绪音乐（-5dB ~ -15dB，动态调整）- 情绪引导

## Integration

- 本 Skill 输出的 `scenes` 数组直接对接 `penta-prompt-generator` 或 `animagine-prompt-enhancer`
- 可选对接 `csv-character-library` 实现角色一致性
- 复用 `dashscope-platform` 的 API Key 管理
- 电影感管线对接: `cinematic_shot_script.py`, `storyboard_generator.py`, `cinematic_post_producer.py`

## Testing

1. 输入简单主题，检查 6 阶段是否完整执行
2. 验证输出包含 metadata、characters、scenes
3. 检查每个分镜包含所有必填字段
4. 验证总时长不超过 max_duration
5. 验证 dialogue_zh 口语化程度
6. 验证 emotion 使用单一情绪词
7. [v3.0] 验证景别递进合理，无连续相同景别
8. [v3.0] 验证每个镜头包含完整的电影感参数
9. [v3.0] 验证情绪曲线与节奏匹配