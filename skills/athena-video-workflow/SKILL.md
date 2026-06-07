---
name: "athena-video-workflow"
description: "Athena AI 角色视频生成工作流。包含模型选择决策、中英双语解耦策略、一键生成脚本指南、电影感管线v2.0支持、PENTA 五层提示词引擎、多分辨率平台变体。Invoke 当用户要生成 AI 角色视频、需要英文口型+中文字幕方案、或参考视频生成最佳实践。"
version: "2.1.0"
dependencies:
  - happyhorse-prompt-library
---

# Athena AI 角色视频生成工作流

> **版本**: 2.0
> **更新日期**: 2026-05-07
> **适用场景**: AI IP 角色宣传视频、品牌故事视频、社交媒体短视频、电影感短视频

---

## 核心策略

**英文口型驱动 + 中文字幕全时段显示**

这是经过 5 个阶段迭代验证的最佳方案：
1. T2V 纯文字生成 → 角色一致性差（40%）
2. I2V 参考图驱动 → 一致性提升至 80%+
3. 竖屏 9:16 适配 → 解决短视频平台需求
4. 中文口型攻坚 → 发现模型能力边界
5. **英文+中文解耦 → 最终方案**

---

## 一键生成

使用 `scripts/clawra/generate_athena_english_cn_subtitles.py`:

```bash
# 生成全部 6 个场景 + 拼接 + 字幕烧录
python3 scripts/clawra/generate_athena_english_cn_subtitles.py \
    --output-dir output/athena_english_cn_subs \
    --duration 10 --resolution 720P \
    --use-portrait-ref --burn-subtitles

# 仅测试单个场景
python3 scripts/clawra/generate_athena_english_cn_subtitles.py \
    --scene 01 --output-dir output/athena_english_cn_subs \
    --duration 10 --resolution 720P --use-portrait-ref
```

---

## 场景定义模板

```python
SCENES = [
    {
        "id": "01", "name": "场景名",
        "action": "动作描述 {speaking_action}",
        "camera": "构图描述（静态镜头）",
        "lighting": "光照描述",
        "dialogue_en": "英文台词（驱动口型）",
        "subtitle_zh": "中文字幕（观众看到）",
        "duration": 10
    },
    # ... 更多场景
]
```

---

## 角色锚点模板

```python
CHARACTER_ANCHOR = (
    "角色名称 + 风格描述: "
    "面部特征（脸型、五官、肤色）, "
    "发型和发色, "
    "标志性配饰（光环、服装图案）, "
    "材质要求（realistic human skin texture, visible pores, "
    "natural subsurface scattering, warm undertone, "
    "subtle skin imperfections, not plastic, not wax-like, not CGI-smooth)"
)
```

---

## 英文口型控制词

```python
ENGLISH_SPEAKING_CONTROL = (
    "speaking English language, lips moving naturally to match English pronunciation, "
    "clear articulation, mouth shapes matching English phonemes, natural speech rhythm, "
    "smooth lip movement, realistic mouth animation"
)
```

---

## ASS 字幕模板

```python
Style: Default,PingFang SC,{fontsize},&H00FFFFFF,&H000000FF,
       &H00000000,&HC0000000,1,0,1,4,2,2,10,10,{margin_v},1

# 全时段字幕策略
for scene in scenes:
    start = scene_index * scene_duration
    end = start + scene_duration
    dialogue: f"Dialogue: 0,{start},{end},Default,,0,0,0,,{scene['zh']}"
```

---

## 质量检查清单

| 检查项 | 标准 | 验证方式 |
|--------|------|---------|
| 分辨率 | 720×1280 (±1px) | ffprobe |
| 时长 | 60s ± 1s | ffprobe |
| 角色一致性 | 跨场景面部差异 < 10% | 人工审核 |
| 字幕可读性 | 所有场景清晰可读 | 人工审核 |
| 字幕时间轴 | 覆盖全部场景 | ASS 文件 |
| 压缩质量 | > 15MB | 文件大小 |

---

## 6 条核心经验

### 1. 选择正确的模型范式
- T2V: 角色一致性 40%，适合一次性/概念性内容
- I2V: 角色一致性 80%+，适合品牌/IP 角色
- **决策**: 角色一致性要求高 → 优先 I2V

### 2. 模型能力边界认知 > 提示词工程
- 不是提示词不够好，是模型不具备能力
- 尝试 3 次失败 → 停止优化提示词 → 寻找替代路径
- **决策**: 绕过问题 > 硬刚问题

### 3. 全时段字幕 > 精确同步字幕
- 中文观众有充足时间阅读（10s vs 传统 3-5s）
- 减少"字幕一闪而过"的阅读焦虑
- **适用**: 品牌宣传、短视频、多语言内容

### 4. 工作流自动化是效率倍增器
- 从手动 30 分钟 → 脚本一键生成
- 错误率降低 90%
- 关键脚本：生成、拼接、字幕

### 5. 成本透明化与控制
- 720P 比 1080P 成本降低 44%
- 先测试单场景再全量
- 预估费用提示 + 余额监控

### 6. 迭代开发模式
- 每次迭代产出可交付物
- v1.0 → v2.0 → v3.0 → 最终方案
- 渐进式验证，非一次性交付

---

## 常见问题

### Q: 如何修改台词？
A: 编辑 `generate_athena_english_cn_subtitles.py` 中的 `SCENES` 列表，修改 `dialogue_en` 和 `subtitle_zh`。

### Q: 如何调整字幕样式？
A: 编辑 `add_athena_subtitles.py` 中的 `generate_ass` 函数，修改 Style 行参数。

### Q: 生成失败怎么办？
A: 检查 API 余额 → 重试单个场景 → 检查网络连接 → 查看错误日志。

### Q: 如何提高角色一致性？
A: 使用高质量参考图 → 强化 CHARACTER_ANCHOR → 考虑 LoRA 训练。

---

## 文件位置

| 文件 | 路径 |
|------|------|
| 一键生成脚本 | `scripts/clawra/generate_athena_english_cn_subtitles.py` |
| I2V 工作流 | `scripts/clawra/generate_athena_i2v_v3.py` |
| 字幕系统 | `scripts/clawra/add_athena_subtitles.py` |
| 视频拼接 | `scripts/clawra/concatenate_videos.py` |
| 参考图 | `assets/athena_ref.jpg`, `output/athena_ref_9x16_crop.jpg` |
| 最终输出 | `output/athena_english_cn_subs/athena_full_story_subtitled.mp4` |

---

*最后更新: 2026-05-06*

---

## v2.0 电影感管线升级

### 核心变化

自 v2.0 起，工作流全面支持电影感管线（Cinematic Pipeline）：

1. **镜头参数化**: 每个场景生成时必须指定景别、角度、焦段、运镜
2. **景别差原则**: 严禁连续两个镜头使用相同景别
3. **专业转场**: 使用 xfade 替代硬切，支持 12 种转场效果
4. **三层声音**: 环境音 + 音效 + 情绪音乐的立体声场

### 电影感管线快速启动

```bash
# 启用电影感管线（第九层）
python3 scripts/clawra/core/end_to_end_drama_pipeline.py \
    --topic "碳硅共生" --scenes 6 \
    --cinematic --transition-duration 1.0 \
    --bgm path/to/bgm.mp3 \
    --ambient-audio path/to/ambient.mp3
```

### 输出文件

执行后将在 `output/cinematic/{topic}_{timestamp}/` 目录下生成：
- `storyboard.json` - 完整分镜数据
- `shot_01-01.mp4` ~ `shot_XX-XX.mp4` - 各镜头视频
- `cinematic_with_transitions.mp4` - 带转场拼接
- `cinematic_final.mp4` - 最终成品（含三层音频）

### 相关文档

- 技术报告: `Athena知识库/.../技术文档/电影感管线升级完成报告.md`
- 执行手册: `Athena知识库/.../技术文档/视听语言与制作管线全面升级执行手册.md`
- 核心模块:
  - `scripts/clawra/core/cinematic_shot_script.py` - 镜头脚本生成
  - `scripts/clawra/core/storyboard_generator.py` - 分镜设计
  - `scripts/clawra/core/sound_designer.py` - 声音设计
  - `scripts/clawra/core/cinematic_post_producer.py` - 后期制作

### 镜头参数速查

| 维度 | 选项 | 说明 |
|:--|:--|:--|
| 景别 | ELS, LS, MS, CU, ECU, MACRO | 远→全→中→近→特→大特 |
| 角度 | eye_level, low, high, dutch, over_shoulder | 平→仰→俯→斜→过肩 |
| 焦段 | 16mm~200mm | 广角→标准→长焦 |
| 运镜 | fixed, dolly_in/out, pan, truck, follow, tilt, crane, handheld, orbit | 10种运镜 |
| 转场 | cut, cross_dissolve, fade, match_cut, j_cut, l_cut | 6种转场 |

### 质量检查新增项

| 检查项 | 标准 | 说明 |
|:--|:--|:--|
| 景别递进 | 无连续相同景别 | 景别差原则 |
| 转场流畅度 | 无生硬切换 | xfade 转场 |
| 三层音频 | 环境音+音效+音乐 | 音量平衡 |
| J/L-Cut | 正确应用 | 声音与画面错位 |

---

## PENTA 五层提示词引擎 (v2.1 新增)

集成于 `agents/video_content_agent/types.py`:

```python
from agents.video_content_agent import PENTAEngine, ScenePlan

penta = PENTAEngine()
scene = ScenePlan(
    scene_id="001",
    scene_name="Carbon Awakening",
    emotion="epic",
    script_line="Athena rises from digital genesis",
    camera="heroic low-angle push-in",
)
prompt = penta.render(scene)
# "MCU trailer aesthetic, cinematic lighting, vertical 9:16, 
#  heroic low-angle push-in, IMAX quality, shallow depth of field. 
#  Athena with obsidian tech-armor..., epic scale, dramatic sky, heroic pose. 
#  HDR volumetric lighting, teal and orange grading, god rays. 
#  8K ultra-detailed, photorealistic CGI. 
#  Scene: Athena rises from digital genesis"
```

### 五层权重

| 层 | 名称 | 权重 | 核心关键词 |
|----|------|:---:|---------|
| L1 | 风格锚定 | 20% | MCU trailer, cinematic lighting |
| L2 | 镜头语言 | 20% | IMAX quality, shallow DOF |
| L3 | 主体刻画 | 25% | obsidian tech-armor, circuit patterns |
| L4 | 光影氛围 | 20% | HDR volumetric, teal & orange |
| L5 | 技术输出 | 15% | 8K photorealistic CGI |

### 情绪修饰符

| 情绪 | 修饰符 |
|------|--------|
| 史诗/epic | "epic scale, dramatic sky, heroic pose" |
| 庄严/solemn | "cathedral lighting, dignified stance" |
| 和谐/harmony | "soft ambient glow, peaceful, nature elements" |
| 前瞻/future | "futuristic horizon, holographic UI elements" |
| 神秘/mystery | "shadow play, enigmatic expression" |

---

## 多平台视频变体 (v2.1 新增)

`agents/video_content_agent/agent.py` — HappyHorseVideoAgent._create_variants():

```python
PLATFORM_VIDEO_SPECS = {
    "twitter": {"max_duration": 140, "aspect": "16:9"},
    "bilibili": {"min_duration": 15, "aspect": "16:9"},
    "tiktok": {"max_duration": 180, "aspect": "9:16"},
    "instagram_reels": {"max_duration": 90, "aspect": "9:16"},
    "xiaohongshu": {"max_duration": 300, "aspect": "3:4"},
}
```

每个平台变体通过 FFmpeg 自动生成:
```bash
ffmpeg -i master.mp4 -c:v libx264 -preset fast -crf 23 \
    -vf "scale='min(720,iw)':-2" platform_variant.mp4
```

## Changelog

### v2.1.0 (2026-05-08)
- 新增 PENTA 五层提示词引擎 (10 emotion modifiers)
- 新增多平台视频变体自动生成 (6平台)
- 集成 VideoContentAgent → ContentDistributionAgent pipeline

### v2.0.0 (2026-05-07)
See frontmatter.
