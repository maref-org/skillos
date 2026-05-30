# Skill: phone-video-factory

## Overview

Phone Agent 驱动手机 App 生成 AI 视频素材的工作流。通过 ADB + VL 视觉模型 + OCR 文字识别，操作豆包、即梦等大厂 App 的原生免费额度生成视频，自动拉取到 Mac 进入后续管线。

核心理念: **薅大厂 App 免费额度，0 API 费用生成视频素材。**

---

## 触发条件

当用户需要以下操作时加载此 Skill:
- 用手机 App 生成 AI 视频
- 从豆包/即梦/千问 App 获取素材
- "薅羊毛"生成视频
- "phone agent 生成视频"
- 需要免费视频素材用于后续剪辑

---

## 平台矩阵

| 平台 | Mode | 免费额度 | 已验证 | 存储路径 |
|------|------|---------|:---:|------|
| **即梦** (jimeng) | t2v / i2v | 每日登录积分 | ✅ | /sdcard/Movies/dreamina_*.mp4 |
| **豆包** (doubao) | t2v / i2v | 每日免费额度 | ✅ | /sdcard/Android/data/com.larus.nova/files/DCIM/nova_video/ |
| 千问 App | t2v | 待验证 | ❌ | 待确认 |
| 剪映 | 一键成片 | 待验证 | ❌ | 待确认 |

---

## 工作流

### 标准流程

```
1. 准备参考图 (I2V模式)
   └─ adb push athena_ref.jpg /sdcard/DCIM/Camera/
   └─ 触发 MediaScanner 扫描

2. 启动 Phone Agent 操作 App
   └─ run_athena.py --task "..." --real --max-steps 25

3. 等待生成完成 + 下载到相册
   └─ Agent 监控页面变化，轮询检测下载按钮

4. 拉取视频到 Mac
   └─ adb pull /sdcard/Movies/dreamina_*.mp4 → comfyui_workspace/input/phone_gen/

5. 清理手机端文件 (可选)
   └─ adb shell rm /sdcard/Movies/dreamina_*.mp4
```

### 使用方式

```bash
# CLI 方式
python agent_system/tools/phone_video_generator.py \
    --platform jimeng_i2v \
    --prompt "银发女性AI角色Athena，冰蓝色发光眼睛，碳纤维外骨骼，科幻电影质感" \
    --push-image /path/to/athena_ref.jpg \
    --pull-video \
    --max-steps 25

# 或通过 Skill 封装的 Python API
from phone_video_factory import PhoneVideoFactory
factory = PhoneVideoFactory(device="R3CR80FKA0V")
result = factory.generate(
    platform="jimeng_i2v",
    prompt="cyberpunk female warrior Athena...",
    image_ref="config/athena_ref.jpg"
)
```

---

## 平台任务模板

### 即梦 文生视频 (jimeng_t2v)
```
打开即梦应用，点击底部AI创作按钮，
选择文生视频功能，
在输入框中输入: {prompt}，
点击生成按钮，等待视频生成完成，
点击下载按钮保存视频
```

### 即梦 图生视频 (jimeng_i2v)
```
打开即梦应用，点击底部AI创作按钮，
选择图生视频功能，
点击上传图片，从相册选择最新的图片，
在提示词输入框中输入: {prompt}，
点击生成按钮，等待视频生成完成，
点击下载按钮保存视频
```

### 豆包 文生视频 (doubao_t2v)
```
打开豆包应用，在首页底部找到AI创作标签并点击，
在AI创作页面选择AI视频功能，
在提示词输入框中输入: {prompt}，
点击生成按钮，等待视频生成完成，
点击下载按钮保存视频到相册
```

### 豆包 图生视频 (doubao_i2v)
```
打开豆包应用，点击底部AI创作标签，
选择AI视频功能，
点击上传图片按钮，从相册选择最新的图片，
在提示词输入框中输入: {prompt}，
点击生成按钮，等待视频生成完成，
点击下载按钮保存视频到相册
```

---

## Compose UI 交互协议 (2026-05-10 验证)

即梦使用 Jetpack Compose 构建 UI，ADB 交互规则与普通 Android View 完全不同。

### 点击方法选择

| 目标 | 方法 | 状态 |
|------|------|:--:|
| 底部 Tab Bar (首页/创作/我的) | `motionevent DOWN→UP` at uiautomator bounds 中心 | ✅ |
| Tab Bar 子元素 (内容区按钮) | ADB 任何方法 | ❌ 不可达 |
| 键盘输入 | ADBKeyboard `am broadcast` (需单引号包裹) | ✅ |
| 物理点击 | Quartz CGEvent / scrcpy HID | ✅ 穿透层 |

### 坐标获取协议

```
❌ 错误: 依赖 VL 模型 (qwen-vl-max-latest) 返回的坐标
   原因: VL 视觉估计偏差 600-835px

✅ 正确: uiautomator dump → 解析 ComposeView bounds → 计算中心
   示例: main_default_tab bounds=[0,2219][1080,2640] → center=(540,2429)
```

### 已验证的即梦坐标 (Z Flip3, 1080×2640)

```python
# uiautomator: main_default_tab bounds=[0,2219][1080,2640]
TAB_BAR = {
    "首页": (180, 2429),
    "创作": (540, 2429),
    "我的": (900, 2429),
}
# motionevent 点击方式
def tap_compose(x, y):
    subprocess.run(["adb", "shell", "input", "motionevent", "DOWN", str(x), str(y)])
    time.sleep(0.1)
    subprocess.run(["adb", "shell", "input", "motionevent", "UP", str(x), str(y)])
```

### ADBKeyboard 文本输入

```bash
# ✅ 正确: 单引号包裹广播参数, 防止 shell 解析逗号/空格
adb shell 'am broadcast -a ADB_INPUT_TEXT --es msg "提示词文本"'

# ❌ 错误: 双引号导致 shell 错误解析
adb shell "am broadcast -a ADB_INPUT_TEXT --es msg \"提示词文本\""
```

### ADB 基础设施修复

```python
# adb_client.py: 自动检测 adb 二进制路径
_ADB_PATHS = [
    os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
    "/opt/homebrew/bin/adb",
    "/usr/local/bin/adb",
    "adb",
]

# agent_loop.py: 双设备时更新 ActionExecutor 的 device_id
self.action_executor.adb_client._device_id_arg = f"-s {actual_device_id}"
```

---

## 已知限制

1. **即梦 UI 基于 Jetpack Compose** — uiautomator 仅能识别主容器 bounds, 子元素全部 `bounds=[0,0]`
2. **Compose Button/FloatingActionButton 不响应 ADB** — 只有 `NavigationBar` 响应 `motionevent`
3. **即梦登录需要抖音 OAuth** — 首次使用需手动扫码授权
4. **豆包需要手机号注册** — 已用 {{PHONE_REPLACED}} 注册
5. **生成耗时不稳定** — 需要 Agent 轮询检测完成状态
6. **免费额度有限** — 建议多平台轮流使用
7. **视频存储路径** — 即梦在 Movies/，豆包在 `/sdcard/Android/data/com.larus.nova/files/DCIM/nova_video/`
8. **即梦 App UI 快速迭代** — Seedance 2.0 模式可能覆盖传统 T2I/I2V 入口
9. **VL 模型坐标不可靠** — 偏差 600-800px, 必须用 uiautomator dump 的 bounds 做最终定位
10. **豆包自动保存** — 视频生成后自动存到 nova_video/ 目录, 无需手动点"保存"按钮

---

## 待扩展平台

- **千问 App**: 通义万相视频生成 (通义千问 App 内)
- **剪映**: 一键成片 + AI 数字人
- **可灵 AI**: 快手 AI 视频生成
- **Pika**: 海外 AI 视频平台

---

---
## 即梦 Web 端替代方案 (macOS)

当 Phone Agent 不可用时, 使用即梦 Web 端 (jimeng.jianying.com) 生成视频。

### 快速手动流程 (Dell 副屏)

```bash
# 1. 在 Dell 显示器打开 Chrome
open -a "Google Chrome" "https://jimeng.jianying.com/ai-tool/home"

# 2. 如果看到 "同意协议后前往登录" 弹窗 → 必须点 "不同意" 关闭
#    ⚠️ 点 "同意" 会触发 OAuth 扫码流程

# 3. 选择模式 → 上传 Athena 参考图 → 输入提示词 → 点 ↑ 发送按钮

# 4. 视频自动下载到 ~/Downloads/jimeng-*.mp4
```

### Web 自动化踩坑要点

| 问题 | 根因 | 状态 |
|------|------|:--:|
| Playwright 点击不触发生成 | React 合成事件不响应 `page.mouse.click()` | ❌ |
| agent-browser 独立 profile | 不共享系统 Chrome 的登录 cookies | ❌ |
| Chrome CDP 不稳定 | macOS `--remote-debugging-port` 启动后立即关闭 | ❌ |
| Quartz CGEvent 底层点击 | 绕过所有框架检测, 直接注入 HID 事件 | ✅ |

### macOS 多显示器坐标

```python
import Quartz
err, displays, count = Quartz.CGGetActiveDisplayList(32, None, None)
for i in range(count):
    bounds = Quartz.CGDisplayBounds(displays[i])
    # Dell 2209WA 竖屏: bounds=(-1050, -159, 1050, 1680)
```

### Quartz 底层点击

```python
def click(x, y):
    for action in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        evt = Quartz.CGEventCreateMouseEvent(None, action, (x, y), 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        time.sleep(0.05)

# Dell 全局坐标 = Dell bounds origin + 截图内坐标
click(-1050 + 274, -159 + 318)  # 点击 Dell 上的 "视频生成" tab
```

---

## 视频合成协议

### 即梦 Web 下载视频自带 AAC 音轨

```bash
# ❌ 错误: -shortest 会保留原视频音轨, 丢弃 TTS
ffmpeg -i video.mp4 -i tts.mp3 -shortest output.mp4

# ✅ 正确: 显式映射流, 丢弃原音轨
ffmpeg -i video.mp4 -i tts.mp3 \
  -map 0:v:0 -map 1:a:0 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -c:a aac output.mp4
```

### 豆包 HEVC 视频转码

豆包生成的视频使用 HEVC 编码, macOS QuickTime 可能无法播放:
```bash
ffmpeg -i doubao_v1.mp4 -c:v libx264 -crf 22 -c:a aac doubao_v1_h264.mp4
```

---

## Changelog

- 2026-05-10: v0.2 — Compose UI 交互协议, 即梦 Web 替代方案, 视频合成协议, 踩坑经验集成
- 2026-05-09: v0.1 — 即梦 I2V 验证通过, 豆包登录通过, Skill 骨架创建

Base directory: [LOCAL_PATH]
