---
name: samsung-oneui-automation
description: "三星 One UI 手机桌面自动化 — ADB + motionevent 拖放、选择模式创建文件夹、IME 切换、uiautomator 元素定位、相机控制。Invoke 当需要自动化三星手机操作、整理桌面、创建文件夹、拖放图标、切换键盘输入文字、拍照等。"
version: "1.0.0"
autoApply: false
dependencies:
  - vl-phone-automation
platforms:
  - claude
  - opencode
triggers:
  - "三星桌面整理"
  - "三星 One UI"
  - "创建文件夹"
  - "拖放图标"
  - "ADB 桌面"
  - "三星自动化"
  - "手机桌面整理"
  - "icon drag"
  - "samsung home screen"
  - "motionevent"
  - "uiautomator 相机"
  - "z flip"
  - "拍照"
  - "前置摄像头"
input_schema:
  type: object
  properties:
    device_id:
      type: string
      description: "ADB 设备序列号"
    task:
      type: string
      enum: [organize_desktop, create_folder, take_photo, set_avatar, rename_account, drag_rearrange]
    page_number:
      type: integer
      description: "目标桌面页号"
sla:
  target_success_rate: 0.85
  max_latency_ms: 15000
changelog:
  - version: "1.0.0"
    date: "2026-05-08"
    changes: "Initial version — Samsung One UI 完整自动化交互模型"
---

# Skill: samsung-oneui-automation

## Overview

三星 Galaxy Z Flip3 One UI 完整的 ADB 自动化交互模型。覆盖桌面整理、文件夹创建、图标拖放重排、IME 键盘切换、相机控制、应用内操作（小红书改名/头像）。

基于真机实验验证的交互模式，非理论推断。

---

## 核心交互模型

### 1. 文件夹创建 (已验证 5 个文件夹)

```
流程: 长按 App 图标 → 弹出菜单"选择" → 点击进入多选模式 → 勾选同类 App → 点"新建文件夹"

关键坐标:
  - "选择"按钮: 弹出后 OCR 定位 (典型 ~247,768)
  - "新建文件夹"按钮: 固定在顶部 (680,238) 附近

代码路径: agent_system/tools/samsung_organizer.py
```

### 2. 图标拖放重排 (已验证 18 个图标)

```
流程: 进入选择模式 → motionevent DOWN→hold→MOVE×N→UP

ADB 命令序列:
  adb shell input motionevent DOWN  <from_x> <from_y>    # 按下
  sleep 0.6                                              # 保持(触发长按拾起)
  adb shell input motionevent MOVE <mid_x> <mid_y>       # 逐步移动×8
  ...
  adb shell input motionevent UP   <to_x>   <to_y>       # 释放

关键: motionevent 不等于 input swipe!
  - input swipe: 轨迹=起点→终点直线, 完成即释放
  - motionevent: 原子操作序列, 可控制按下/移动/释放分开
```

### 3. 选择模式入口

```
方式 A (推荐): 长按任意 App → 弹出菜单 → 点"选择"
方式 B: 长按桌面空白 → 底部菜单(壁纸/主题/小组件/设置)

注意: 三星长按空白处不直接进入编辑模式(不像原生Android),
      而是显示底部菜单。要拖放图标需通过"选择"模式。
```

### 4. IME 键盘切换 (输入英文)

```
问题: 三星中文键盘(HoneyBoard)拦截 input text/keyevent, 
      将英文转为中文候选或乱码

解决方案:
  # 列出可用键盘
  adb shell ime list -s

  # 切换到 SwiftKey (接收原始 ASCII)
  adb shell ime set com.touchtype.swiftkey/com.touchtype.KeyboardService

  # 输入文本
  adb shell cmd input text "Athena"

  # 恢复三星键盘
  adb shell ime set com.samsung.android.honeyboard/.service.HoneyBoardService

可用键盘:
  - com.samsung.android.honeyboard/.service.HoneyBoardService (三星·中文)
  - com.touchtype.swiftkey/com.touchtype.KeyboardService (SwiftKey)
  - com.tencent.wetype/.plugin.hld.WxHldService (微信输入法)
```

### 5. uiautomator 元素定位

```
无文字的元素(图标/按钮)通过 uiautomator dump 定位:

  adb shell uiautomator dump /sdcard/ui.xml
  adb pull /sdcard/ui.xml /tmp/ui.xml

查找关键元素:
  - 相机切换按钮: resource-id="switch_camera_button", bounds=[804,2047][1008,2251]
  - 小红书"我"tab: content-desc="我", bounds=[864,2361][1080,2496]
  - 小红书"编辑资料": text="编辑资料"
  - 小红书"完成"按钮: text="完成", bounds=[855,2385][1035,2475]
```

### 6. 相机控制

```
打开相机:
  adb shell am start -a android.media.action.STILL_IMAGE_CAMERA

后置拍照:
  adb shell input keyevent 27    # KEYCODE_CAMERA

前置拍照:
  1. 打开相机
  2. 点切换按钮: adb shell input tap 906 2149
     (uiautomator: switch_camera_button, center 906,2149)
  3. 拍照: adb shell input keyevent 27

注意: CAMERA_FACING intent extra 在三星上不生效, 必须用点击切换按钮
```

### 7. 边缘安全区域

```
三星 Z Flip3 屏幕: 1080×2640

边缘限制 (action_executor.py EDGE_MARGIN_RATIO):
  - 水平: 54px (5%) — 保护手势返回区域
  - 顶部: 52px (2%) — 允许触达顶部图标行
  - 底部: 132px (5%) — 保护导航栏

如果需要点击边缘附近 (如顶部 app 图标 y<132):
  - 配置 EDGE_MARGIN_RATIO 或使用 _validate_coords 自定义
```

---

## 完整示例

### 创建购物文件夹
```python
from agent_system.tools.samsung_organizer import SamsungDesktopOrganizer
org = SamsungDesktopOrganizer(device_id="R3CR80FKA0V", dry_run=False)
org.scan_all_pages()
org.compact_page(page_num=2)
```

### 设置小红书头像
```python
# 1. 裁剪头像 400x400
from PIL import Image
img = Image.open("athena_portrait.jpg")
cropped = img.crop((left, top, left+min(w,h), top+min(w,h)))
avatar = cropped.resize((400, 400), Image.LANCZOS)
avatar.save("/tmp/avatar.jpg")

# 2. 推送到手机
adb push /tmp/avatar.jpg /sdcard/Pictures/

# 3. 触发媒体扫描
adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE \
    -d file:///sdcard/Pictures/avatar.jpg

# 4. 小红书: 我→头像→上传新头像→相册→裁剪→完成
```

---

## 测试清单

- [ ] 创建文件夹: 长按 App → 选择 → 选中 → 新建文件夹
- [ ] 拖放图标: 选择模式 motionevent 序列
- [ ] compact_page: 自动紧凑排列整页
- [ ] IME 切换: HoneyBoard → SwiftKey → 恢复
- [ ] 拍照: 后置 + 前置
- [ ] uiautomator dump: 找到无文字 UI 元素坐标

## Changelog

See frontmatter.
