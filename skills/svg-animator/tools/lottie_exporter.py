#!/usr/bin/env python3
"""Lottie JSON 导出工具。

将 SVG/CSS 动画转换为 Lottie 格式（Bodymovin v5.0+）。
"""

import json
from pathlib import Path
from typing import Any


def export_lottie(animation_html: str, output_path: Path) -> Path:
    """将 HTML/SVG 动画导出为 Lottie JSON。

    MVP 版本：生成基础 Lottie 骨架，后续接入完整转换逻辑。

    Args:
        animation_html: HTML/SVG 动画内容
        output_path: 输出路径

    Returns:
        输出文件路径
    """
    # MVP: 生成基础 Lottie JSON 骨架
    lottie_data = _create_lottie_skeleton(animation_html)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(lottie_data, indent=2))

    return output_path


def _create_lottie_skeleton(html_content: str) -> dict[str, Any]:
    """创建 Lottie JSON 骨架。

    Lottie 格式基于 Bodymovin v5.0+ schema。
    """
    return {
        "v": "5.7.4",  # Lottie 版本
        "fr": 30,  # 帧率
        "ip": 0,  # 入点帧
        "op": 60,  # 出点帧（2秒 @ 30fps）
        "w": 300,  # 宽度
        "h": 300,  # 高度
        "nm": "SVG Animation",  # 名称
        "ddd": 0,  # 3D 开关
        "assets": [],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 4,  # Shape layer
                "nm": "Animated Shape",
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100},  # Opacity
                    "r": {"a": 0, "k": 0},  # Rotation
                    "p": {"a": 0, "k": [150, 150, 0]},  # Position
                    "a": {"a": 0, "k": [0, 0, 0]},  # Anchor point
                    "s": {"a": 0, "k": [100, 100, 100]},  # Scale
                },
                "shapes": [],
                "ip": 0,
                "op": 60,
                "st": 0,
                "bm": 0,
            }
        ],
        "markers": [],
    }


def svg_path_to_lottie_shape(svg_path_data: str) -> dict[str, Any]:
    """将 SVG path 数据转换为 Lottie shape。

    Args:
        svg_path_data: SVG path 的 d 属性值

    Returns:
        Lottie shape 字典
    """
    return {
        "ty": "sh",  # Shape
        "d": 1,
        "closed": True,
        "ks": {
            "a": {"a": 0, "k": []},  # Vertices (需要解析 path data)
            "c": {"a": 0, "k": True},  # Closed
            "ix": 1,
        },
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python lottie_exporter.py <input.html> <output.json>")
        sys.exit(1)

    from pathlib import Path

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    html_content = input_path.read_text()
    result = export_lottie(html_content, output_path)
    print(f"Lottie JSON exported to: {result}")
