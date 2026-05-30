"""
Phone Video Factory — 平台能力速查表

记录各平台免费额度、限制、API信息，避免重复查询。
"""

PLATFORM_CAPABILITIES = {
    "jimeng": {
        "name": "即梦 AI",
        "package": "com.bytedance.dreamina",
        "free_quota": "每日登录积分，约 5-10 次生成",
        "video_format": "MP4 H.264 AAC",
        "video_duration": "4-6 秒",
        "video_resolution": "~720p (720×1280 竖屏)",
        "storage_path": "/sdcard/Movies/dreamina_*.mp4",
        "login_method": "抖音 OAuth",
        "ui_type": "Jetpack Compose (NavigationBar + Button/FAB)",
        "verified": True,
        "compose_tab_bar": "✅ motionevent at [0,2219][1080,2640]",
        "compose_buttons": "❌ ADB 不可达 (需要 Quartz CGEvent / scrcpy HID)",
        "web_version": "jimeng.jianying.com (H.264 60fps 自带AAC音轨)",
        "web_download": "~/Downloads/jimeng-*.mp4",
        "notes": "UI 快速迭代; Seedance 2.0 可能覆盖传统入口; VL 坐标偏差 600-835px",
    },
    "doubao": {
        "name": "豆包",
        "package": "com.larus.nova",
        "free_quota": "每日免费次数 (约 10 次)",
        "video_format": "MP4 HEVC (需转码为 H.264)",
        "video_duration": "3-5 秒",
        "video_resolution": "720×960 (3:4, 非9:16)",
        "storage_path": "/sdcard/Android/data/com.larus.nova/files/DCIM/nova_video/",
        "login_method": "手机号 + SMS",
        "ui_type": "原生 + WebView 混合",
        "verified": True,
        "auto_save": "✅ 生成后自动保存, 无需手动点'保存'按钮",
        "codec_fix": "ffmpeg -i in.mp4 -c:v libx264 -c:a aac out.mp4",
    },
    "qianwen_app": {
        "name": "通义千问 App",
        "package": "com.alibaba.tongyi",
        "free_quota": "待验证",
        "video_format": "待确认",
        "video_duration": "待确认",
        "video_resolution": "待确认",
        "storage_path": "待确认",
        "login_method": "阿里云账号",
        "ui_type": "原生",
        "verified": False,
        "notes": "通义万相视频生成功能需验证",
    },
    "jianying": {
        "name": "剪映",
        "package": "com.lemon.lv",
        "free_quota": "基本免费",
        "video_format": "MP4 H.264",
        "video_duration": "不限",
        "video_resolution": "1080p+",
        "storage_path": "/sdcard/Movies/ / DCIM/",
        "login_method": "抖音账号",
        "ui_type": "原生",
        "verified": False,
        "notes": "一键成片 + AI数字人功能需验证",
    },
}

# 设备信息
ZFLIP3_DEVICE = {
    "id": "R3CR80FKA0V",
    "model": "SM-F711N",
    "resolution": "1080x2640",
    "android_version": "14",
    "adb_transport": "usb",
}
