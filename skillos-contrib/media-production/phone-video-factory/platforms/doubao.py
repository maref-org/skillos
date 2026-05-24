"""
豆包 (Doubao) — Phone Agent I2V/T2V 工作流

平台信息:
  - App: 豆包 (字节跳动)
  - 包名: com.larus.nova
  - 登录方式: 手机号 + 短信验证码
  - 已注册账号: {{PHONE_REPLACED}}
  - UI 类型: 原生 + WebView 混合
  - 免费额度: 每日免费次数 (~10 次)

已验证:
  - ✅ App 安装 (应用商店搜索)
  - ✅ 手机号注册 + SMS 验证码
  - ✅ 登录
  - ✅ 视频生成
  - ⚠️ 生成后自动保存到 nova_video/, 无需手动点"保存"
  - ❌ HEVC 编码需 ffmpeg 转码为 H.264

已知限制:
  - HEVC 编码: macOS QuickTime 无法播放, 需转码
  - 视频分辨率: 720×960 (3:4, 非标准 9:16)
"""

import logging

logger = logging.getLogger(__name__)

# 豆包自动保存路径 (2026-05-10 实测确认)
# 视频生成后自动存入此目录, 无需手动点击"保存"按钮
DOUBAO_AUTO_SAVE = (
    "/sdcard/Android/data/com.larus.nova/files/DCIM/nova_video/"
)

# ⚠️ 以下坐标均为 VL 模型早期估计值
# 已知 VL 模型坐标偏差 600-835px (参考 SKILL.md Compose 交互协议)
# 不要直接用 — 需 uiautomator dump 重新验证
DOUBAO_UI_HINTS_UNVERIFIED = {
    "ai_tab": (360, 2490),
    "video_function": (540, 1500),
    "image_upload": (540, 1800),
    "prompt_input": (540, 2100),
    "generate_button": (540, 2280),
}


def build_doubao_task(
    mode: str = "i2v",
    prompt: str = "",
    has_ref_image: bool = False,
) -> str:
    """
    构建豆包视频生成的任务描述

    Args:
        mode: "t2v" 或 "i2v"
        prompt: 提示词
        has_ref_image: 是否已推送参考图

    Returns:
        任务描述字符串
    """
    if mode == "i2v":
        base = (
            "打开豆包应用，点击底部AI创作标签，"
            "选择AI视频功能，"
        )
        if has_ref_image:
            base += "点击上传图片按钮，从相册选择最新的图片，"
        base += (
            f"在提示词输入框中输入: {prompt}，"
            "点击生成按钮，等待视频生成完成"
        )
        return base
    else:
        return (
            "打开豆包应用，在首页底部找到AI创作标签并点击，"
            "在AI创作页面选择AI视频功能，"
            f"在提示词输入框中输入: {prompt}，"
            "点击生成按钮，等待视频生成完成"
        )
