# 即梦 App 视频生成工作流 Skill

## 概述

自动化即梦 App 视频生成流程，支持多视频故事生成、视频拉取、合成配音。

**适用场景**:
- AI 角色视频生成
- 多场景故事视频制作
- 批量视频内容生产

**设备要求**:
- Samsung Z Flip3 (1080x2640)
- ADB 调试已开启
- 即梦 App 已安装

---

## 核心工作流

### 1. 导航路径（已验证）

```
即梦 App 首页 → 底部中间"创作"按钮 (540, 2174) → 视频生成页面
```

**关键坐标**:
- 底部创作按钮: `(540, 2174)`
- 提示词输入框: `(739, 2353)`
- 生成按钮: 动态定位（通常在底部）
- 关闭弹窗: `(55, 115)`

### 2. Phase 流程

| Phase | 名称 | 关键操作 | 验证方法 |
|-------|------|----------|----------|
| 1 | 启动 App | `am start` 启动即梦 | Activity 检查 |
| 2 | 进入视频生成 | 点击 (540, 2174) | UI 树包含"视频生成" |
| 3 | 上传参考图 | Push 图片 + 半自动选择 | 等待 30s |
| 4 | 输入提示词 | ADB 键盘输入 | 文本确认 |
| 5 | 生成并等待 | 点击生成 + 轮询检测 | 检测"再次生成"等关键词 |
| 6 | 拉取视频 | `adb pull` + 去重 | 文件大小检查 |

### 3. 免费额度限制

**重要**: 即梦 App 每日免费额度仅 **1 次视频生成**。

- 多视频故事需分多天生成
- 或购买会员获取积分
- 生成失败（额度不足）会提示"免费次数已用完"

---

## 代码实现

### 基础工作流类

```python
class JimengAppWorkflow:
    def __init__(self, device: str, mode: str = "semi", output_dir: str):
        self.device = device
        self.mode = mode  # "auto" or "semi"
        self.output_dir = output_dir
        self.existing_videos = set()  # 视频去重
        
    def execute(self, ref_path: str, prompt: str) -> Dict:
        # Phase 1-6 顺序执行
        phases = [
            self.phase1_launch_app,
            self.phase2_open_video_editor,
            self.phase3_upload_ref,
            self.phase4_input_prompt,
            self.phase5_generate_and_wait,
            self.phase6_pull_video,
        ]
```

### 关键修复点

#### 1. Phase 2: 正确导航
```python
def phase2_open_video_editor(self):
    # 点击底部中间"创作"按钮
    self._tap_xy(540, 2174)
    time.sleep(5)
    
    # 验证进入视频生成页面
    xml = self._dump()
    if xml and ("视频生成" in xml or "请描述画面内容" in xml):
        return PhaseResult(2, "已进入视频生成", True, ...)
```

#### 2. Phase 5: 完成检测
```python
def phase5_generate_and_wait(self):
    # 轮询检测完成状态
    while waited < GENERATION_TIMEOUT:
        xml = self._dump()
        if xml and any(k in xml for k in ["重新编辑", "再次生成", "下载", "保存"]):
            return PhaseResult(5, "生成完成", True, ...)
```

#### 3. Phase 6: 视频去重
```python
def _find_latest_video(self):
    for pattern in VIDEO_PATHS:
        videos = self._adb(f"shell ls -t {pattern}").stdout.split('\n')
        for video in videos:
            if video not in self.existing_videos:
                return video
    return None
```

---

## 多视频编排

### 故事生成配置

```python
STORY_CONFIG = {
    "title": "Athena 拉花咖啡教学",
    "scenes": [
        {
            "scene_id": 1,
            "name": "准备阶段",
            "prompt": "高清人像，Athena 穿着白色棉质休闲衬衫..."
        },
        {
            "scene_id": 2,
            "name": "拉花手法",
            "prompt": "高清人像，Athena 穿着白色休闲衬衫..."
        },
        {
            "scene_id": 3,
            "name": "成品展示",
            "prompt": "高清人像，Athena 完成心形拉花..."
        }
    ]
}
```

### 执行策略

1. **单视频模式**: 每天生成 1 个场景（免费额度限制）
2. **多日连续**: 记录进度，次日继续生成
3. **会员模式**: 购买积分后可批量生成

---

## 视频合成

### FFmpeg 合成脚本

```bash
# 1. 合并视频（带转场）
ffmpeg -i scene1.mp4 -i scene2.mp4 -i scene3.mp4 \
  -filter_complex "[0:v][1:v]xfade=transition=fade:duration=1:offset=5[v01]; \
                   [v01][2:v]xfade=transition=fade:duration=1:offset=9[vout]" \
  -map "[vout]" output.mp4

# 2. 生成配音
say -v Ting-Ting -o voiceover.aiff "配音文本"

# 3. 混合音频
ffmpeg -i output.mp4 -i voiceover.mp3 -i bgm.m4a \
  -filter_complex "[1:a]volume=1.0[voice]; [2:a]volume=0.25[bgm]; \
                   [voice][bgm]amix=inputs=2[audio]" \
  -map 0:v -map "[audio]" final.mp4
```

---

## 故障排查

### 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 进入错误页面 | 点击了底部"+"按钮 | 改为点击 (540, 2174) |
| 视频重复 | 未去重 | 使用 `existing_videos` 集合 |
| 生成超时 | 额度不足/网络问题 | 检查 App 提示，重试 |
| 设备离线 | USB 连接问题 | `adb kill-server && adb start-server` |
| 屏幕休眠 | 未设置常亮 | `settings put system screen_off_timeout 2147483647` |

### 调试命令

```bash
# 检查设备连接
adb devices -l

# 查看当前 Activity
adb shell dumpsys window | grep mCurrentFocus

# Dump UI 树
adb shell uiautomator dump /sdcard/ui.xml
adb pull /sdcard/ui.xml /tmp/ui.xml

# 截图
adb shell screencap -p /sdcard/screen.png
adb pull /sdcard/screen.png /tmp/screen.png

# 查看视频文件
adb shell ls -lt /sdcard/Movies/dreamina_*.mp4
```

---

## 最佳实践

1. **生成前准备**:
   - 设置屏幕常亮
   - 确保设备连接稳定
   - 清理旧视频文件

2. **提示词优化**:
   - 包含具体视觉描述（服装、动作、背景）
   - 长度控制在 50-100 字
   - 使用"高清人像"等质量关键词

3. **多视频策略**:
   - 每天生成 1 个场景（免费额度）
   - 记录生成进度
   - 使用统一输出目录

4. **视频管理**:
   - 使用日期命名输出目录
   - 保留原始视频和合成视频
   - 定期清理临时文件

---

## 文件结构

```
agent_system/mcp/tools/
├── jimeng_app_workflow.py          # 原始工作流
├── jimeng_app_workflow_fixed.py    # 修复版工作流
└── multi_video_story.py            # 多视频编排

scripts/
└── merge_story_video_v3.sh         # 视频合成脚本

comfyui_workspace/
├── input/phone_gen/                # 原始视频
└── output/                         # 合成视频
```

---

## 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-05-16 | v1.0 | 初始版本，修复导航路径、视频去重、完成检测 |
| 2026-05-16 | v1.1 | 确认免费额度限制（1 次/天） |
