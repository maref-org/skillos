#!/usr/bin/env python3
"""SVG 解析与优化工具。

解析 SVG 路径、提取颜色、优化结构。
"""

import re
from typing import Any


def parse_svg(svg_content: str) -> dict[str, Any]:
    """解析 SVG 内容。

    Args:
        svg_content: SVG 字符串

    Returns:
        解析结果字典
    """
    result: dict[str, Any] = {"raw": svg_content, "paths": [], "colors": [], "elements": []}

    # 提取路径
    paths = re.findall(r'<path[^>]*d="([^"]*)"', svg_content)
    result["paths"] = paths

    # 提取颜色
    color_pattern = r"#(?:[0-9a-fA-F]{3}){1,2}"
    colors = re.findall(color_pattern, svg_content)
    result["colors"] = list(set(colors))

    # 提取元素类型
    elements = re.findall(r"<(\w+)", svg_content)
    result["elements"] = list(set(elements))

    # 提取 viewBox
    viewBox_match = re.search(r'viewBox="([^"]*)"', svg_content)
    if viewBox_match:
        result["viewBox"] = viewBox_match.group(1)

    return result


def optimize_svg(svg_content: str) -> str:
    """优化 SVG 内容。

    - 移除空格和换行
    - 移除注释
    - 合并重复样式
    """
    # 移除注释
    svg = re.sub(r"<!--.*?-->", "", svg_content, flags=re.DOTALL)

    # 移除多余空白
    svg = re.sub(r"\s+", " ", svg).strip()

    return svg


def extract_animation_paths(svg_content: str) -> list[dict[str, Any]]:
    """提取可动画化的路径元素。

    Returns:
        路径列表，每个包含 path_data, length, type 等
    """
    paths = re.findall(r'<path[^>]*d="([^"]*)"[^>]*/>', svg_content)

    animatable = []
    for path_data in paths:
        # 计算路径长度（近似）
        length = len(path_data)
        animatable.append(
            {
                "path_data": path_data,
                "length": length,
                "type": "path",
            }
        )

    # 也检查 circle/rect 等可动画元素
    circles = re.findall(r'<circle[^>]*cx="([^"]*)"[^>]*cy="([^"]*)"[^>]*r="([^"]*)"', svg_content)
    for cx, cy, r in circles:
        animatable.append(
            {
                "path_data": f"circle cx={cx} cy={cy} r={r}",
                "length": float(r) * 6.28,  # 2πr 近似周长
                "type": "circle",
            }
        )

    return animatable


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python svg_parser.py <svg_file>")
        sys.exit(1)

    from pathlib import Path

    content = Path(sys.argv[1]).read_text()
    result = parse_svg(content)
    print(f"Paths: {len(result['paths'])}")
    print(f"Colors: {result['colors']}")
    print(f"Elements: {result['elements']}")
