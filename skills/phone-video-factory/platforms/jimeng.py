"""
即梦 (Jimeng / Dreamina) — Phone Agent I2V/T2V 工作流

平台信息:
  - App 包名: com.bytedance.dreamina
  - 内部代号: dreamina
  - 视频路径: /sdcard/Movies/dreamina_{id}_{ts}_m.mp4
  - 登录方式: 抖音 OAuth (需手动首次授权)
  - UI 类型: Jetpack Compose (uiautomator 仅能取到容器 bounds)
  - 免费额度: 每日登录积分

已验证:
  - ✅ App 安装 (浏览器下载 APK)
  - ✅ 抖音 OAuth 登录 (多次尝试后通过)
  - ✅ 主 tab 切换 (motionevent + uiautomator bounds)
  - ✅ 视频下载到 Movies/
  - ✅ adb pull 到 Mac
  - ⚠️ Compose 内容区按钮 (+/图片生成/生成) 不响应 ADB 输入

Compose 交互协议 (2026-05-10):
  1. tab bar: motionevent at uiautomator bounds center ✅
  2. 内容区 Button/FloatingActionButton: ADB 不可达 ❌
  3. 坐标: 用 uiautomator dump bounds, 不用 VL 模型 ❌
  4. 文本输入: ADBKeyboard 单引号广播 ✅
  5. 替代: 即梦 Web (jimeng.jianying.com) + Dell Chrome 手动 ✅

即梦 Web 自动下载路径:
  ~/Downloads/jimeng-*.mp4
  格式: H.264 60fps, 自带 AAC 音轨 (需 -map 0:v:0 -map 1:a:0 替换配音)

已知限制:
  - App UI 快速迭代 (Seedance 2.0 可能覆盖传统入口)
  - VL 模型坐标偏差 600-835px, 不可用于精确定位
  - 生成等待时间不可预测
"""

import logging
import subprocess
import time

logger = logging.getLogger(__name__)

# 即梦视频在手机上的存储路径
JIMENG_VIDEO_PATH = "/sdcard/Movies"
JIMENG_VIDEO_PATTERN = "dreamina_*.mp4"

# ═══════════════════════════════════════════════════════════
# Compose UI 交互协议 — 基于 uiautomator dump 的真坐标
# ═══════════════════════════════════════════════════════════

# 主 Tab Bar (Jetpack Compose NavigationBar)
# uiautomator: main_default_tab bounds=[0,2219][1080,2640]
# ✅ motionevent 可点击 | ❌ input tap 无效
TAB_BAR = {
    "首页": (180, 2429),
    "创作": (540, 2429),
    "我的": (900, 2429),
}
TAB_BAR_BOUNDS = (0, 2219, 1080, 2640)

# 内容区按钮 (y=1500-1600)
# ❌ 所有 ADB 方法均无效 (input tap / motionevent / long-press)
# 需要: Quartz CGEvent (macOS) / scrcpy HID / 真手指触摸
CONTENT_BUTTONS = {
    "图片生成": (275, 1568),  # VL 多次确认, 实际位置因页面变化
    "添加参考图": (98, 1568),  # +号按钮
    "提示词输入": (397, 1568),  # 提示区域
    "生成": (615, 1521),  # Seedance 2.0 生成按钮
}


def tap_compose(x: int, y: int, device: str = "R3CR80FKA0V") -> bool:
    """
    Compose 兼容点击 — 使用 motionevent 而非 input tap

    适用: Compose NavigationBar (tab bar)
    不适用: Compose Button / FloatingActionButton (内容区按钮)
    """
    for action in ("DOWN", "UP"):
        r = subprocess.run(
            ["adb", "-s", device, "shell", "input", "motionevent", action, str(x), str(y)],
            capture_output=True,
            timeout=5,
        )
        if r.returncode != 0:
            return False
        time.sleep(0.08)
    return True


def switch_tab(tab_name: str, device: str = "R3CR80FKA0V") -> bool:
    """切换到指定 tab (首页/创作/我的)"""
    if tab_name not in TAB_BAR:
        return False
    x, y = TAB_BAR[tab_name]
    return tap_compose(x, y, device)


def input_text_adbkeyboard(text: str, device: str = "R3CR80FKA0V") -> bool:
    """
    通过 ADBKeyboard 输入文字
    ⚠️ 必须用单引号包裹整个 am broadcast 命令, 防止 shell 解析空格/逗号
    """
    cmd = f"am broadcast -a ADB_INPUT_TEXT --es msg '{text}'"
    r = subprocess.run(["adb", "-s", device, "shell", cmd], capture_output=True, timeout=5)
    return r.returncode == 0


def get_jimeng_cleanup_command() -> str:
    """获取清理手机端即梦视频的命令"""
    return f"adb shell rm {JIMENG_VIDEO_PATH}/dreamina_*.mp4"


def build_jimeng_task(
    mode: str = "i2v",
    prompt: str = "",
    has_ref_image: bool = False,
) -> str:
    """
    构建即梦视频生成的任务描述 (自然语言)

    ⚠️ Compose 限制: 即梦 UI 使用 Jetpack Compose，
    底部 Tab Bar 可 ADB 操作，但内容区按钮 (生成/上传/+)
    不响应任何 ADB 方法 (详见 SKILL.md Compose 交互协议)。
    建议配合即梦 Web 端 (jimeng.jianying.com) 或 Quartz CGEvent 使用。

    Args:
        mode: "t2v" (文生视频) 或 "i2v" (图生视频)
        prompt: 提示词 (中文)
        has_ref_image: 是否已推送参考图到手机相册

    Returns:
        任务描述字符串, 传给 run_athena.py --task
    """
    if mode == "i2v":
        if has_ref_image:
            return (
                "打开即梦应用，点击底部AI创作按钮，"
                "选择图生视频功能，"
                "点击上传图片，从相册选择最新的图片，"
                f"在提示词输入框中输入: {prompt}，"
                "点击生成按钮，等待视频生成完成，"
                "点击下载按钮保存视频到相册"
            )
        else:
            return (
                "打开即梦应用，点击底部AI创作按钮，"
                f"选择图生视频功能，在输入框中输入: {prompt}，"
                "点击生成按钮，等待视频生成完成，下载视频到相册"
            )
    else:
        return (
            "打开即梦应用，点击底部AI创作按钮，"
            "选择文生视频功能，"
            f"在输入框中输入: {prompt}，"
            "点击生成按钮，等待视频生成完成，"
            "点击下载按钮保存视频到相册"
        )


def get_jimeng_pull_command(local_dir: str) -> str:
    """获取拉取即梦视频的 adb 命令"""
    return f"adb pull {JIMENG_VIDEO_PATH}/dreamina_*.mp4 {local_dir}/"
