"""
Phone Video Factory — ADB 媒体工具

从手机拉取视频到 Mac、推送参考图到手机。
已验证路径:
  - 即梦: /sdcard/Movies/dreamina_*.mp4
  - 豆包: /sdcard/DCIM/Camera/*.mp4 (待确认)
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认 Mac 端输出目录
DEFAULT_OUTPUT_DIR = Path(os.environ.get("PHONE_VIDEO_OUTPUT_DIR", "./output/phone_gen"))

# 手机端已知视频路径 (按优先级排序)
PHONE_VIDEO_PATHS = [
    "/sdcard/Movies/dreamina_*.mp4",  # 即梦
    "/sdcard/Android/data/com.larus.nova/files/DCIM/nova_video/*.mp4",  # 豆包自动保存
    "/sdcard/Movies/*.mp4",  # 其他 App (Movies)
    "/sdcard/DCIM/Camera/*.mp4",  # 相机
    "/sdcard/Download/*.mp4",  # 下载
]


def pull_latest_videos(
    device: str,
    output_dir: str | None = None,
    pattern: str | None = None,
) -> list[Path]:
    """
    从手机拉取最新视频到 Mac

    Args:
        device: ADB 设备 ID (如 R3CR80FKA0V)
        output_dir: Mac 端输出目录
        pattern: 手机端文件 glob 模式 (如 dreamina_*.mp4)

    Returns:
        已拉取的文件路径列表
    """
    dest = Path(output_dir or DEFAULT_OUTPUT_DIR)
    dest.mkdir(parents=True, exist_ok=True)

    paths = [pattern] if pattern else PHONE_VIDEO_PATHS
    pulled = []

    for glob_pattern in paths:
        try:
            # 列出手机上的文件
            result = subprocess.run(
                ["adb", "-s", device, "shell", "ls", "-t", glob_pattern],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue

            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

            for f in files:
                filename = Path(f).name
                dest_file = dest / filename

                if dest_file.exists():
                    logger.info(f"Already pulled: {filename}")
                    pulled.append(dest_file)
                    continue

                pull_result = subprocess.run(
                    ["adb", "-s", device, "pull", f, str(dest_file)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if pull_result.returncode == 0 and dest_file.exists():
                    logger.info(f"Pulled: {filename} ({dest_file.stat().st_size:,} bytes)")
                    pulled.append(dest_file)

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout listing files: {glob_pattern}")
        except Exception as e:
            logger.error(f"Failed to pull from {glob_pattern}: {e}")

    return pulled


def push_reference_image(device: str, image_path: str) -> bool:
    """
    推送参考图到手机相册

    Args:
        device: ADB 设备 ID
        image_path: Mac 端图片路径

    Returns:
        是否成功
    """
    src = Path(image_path)
    if not src.exists():
        logger.error(f"Reference image not found: {image_path}")
        return False

    dest_phone = f"/sdcard/DCIM/Camera/{src.name}"

    try:
        result = subprocess.run(
            ["adb", "-s", device, "push", str(src), dest_phone],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False

        # 触发媒体扫描让相册识别新文件
        subprocess.run(
            [
                "adb",
                "-s",
                device,
                "shell",
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                f"file://{dest_phone}",
            ],
            capture_output=True,
            timeout=10,
        )
        logger.info(f"Pushed reference image: {src.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to push image: {e}")
        return False


def cleanup_phone_videos(device: str, pattern: str = None) -> int:
    """
    清理手机端的视频文件

    Args:
        device: ADB 设备 ID
        pattern: 要删除的文件模式

    Returns:
        删除的文件数
    """
    patterns = [pattern] if pattern else PHONE_VIDEO_PATHS
    deleted = 0

    for p in patterns:
        try:
            result = subprocess.run(
                ["adb", "-s", device, "shell", f"rm {p}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                deleted += 1
        except Exception as e:
            logger.error(f"Failed to cleanup {p}: {e}")

    return deleted
