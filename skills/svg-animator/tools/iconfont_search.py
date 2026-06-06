#!/usr/bin/env python3
"""图标搜索工具 — 支持多源：Lucide / Simple Icons / Iconfont（可选）。

优先使用开源图标库（无需认证），Iconfont 作为可选后端。
"""

import json
import urllib.parse
import urllib.request
from typing import Any

# ── 图标源配置 ──
ICON_SOURCES = {
    "lucide": {
        "base_url": "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons",
        "index_url": "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/index.json",
        "enabled": True,
    },
    "simple-icons": {
        "base_url": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons",
        "index_url": "https://cdn.jsdelivr.net/npm/simple-icons@latest/_data/simple-icons.json",
        "enabled": True,
    },
    "iconfont": {
        "search_url": "https://www.iconfont.cn/api/icon/search",
        "enabled": False,  # 需要登录态，默认关闭
    },
}


def search_icons(query: str, limit: int = 10, source: str = "all") -> list[dict[str, Any]]:
    """搜索图标。

    Args:
        query: 搜索关键词
        limit: 返回结果数量上限
        source: 图标源 ("lucide" | "simple-icons" | "iconfont" | "all")

    Returns:
        图标列表
    """
    results = []

    sources_to_search = [s for s in ICON_SOURCES if s == source] if source != "all" else ["lucide", "simple-icons"]

    for src in sources_to_search:
        if not ICON_SOURCES[src].get("enabled", False):
            continue

        if src == "lucide":
            results.extend(_search_lucide(query, limit))
        elif src == "simple-icons":
            results.extend(_search_simple_icons(query, limit))
        elif src == "iconfont":
            results.extend(_search_iconfont(query, limit))

        if len(results) >= limit:
            break

    return results[:limit]


def _search_lucide(query: str, limit: int) -> list[dict[str, Any]]:
    """搜索 Lucide 图标库（开源，MIT 协议）。"""
    try:
        # Lucide 图标以单独 SVG 文件存储在 GitHub
        # 通过文件名匹配搜索
        url = "https://api.github.com/repos/lucide-icons/lucide/contents/icons?per_page=100"
        req = urllib.request.Request(url, headers={"User-Agent": "svg-animator/0.1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            files = json.loads(resp.read())

        # 过滤匹配的图标
        query_lower = query.lower()
        matched = []
        for f in files:
            name = f["name"].replace(".svg", "")
            if query_lower in name.lower():
                matched.append({
                    "id": f"lucide-{name}",
                    "name": name,
                    "source": "lucide",
                    "svg_url": f["download_url"],
                    "license": "MIT",
                })
                if len(matched) >= limit:
                    break

        return matched
    except Exception as e:
        print(f"[icon_search] Lucide search failed: {e}")
        return []


def _search_simple_icons(query: str, limit: int) -> list[dict[str, Any]]:
    """搜索 Simple Icons（品牌图标，开源）。"""
    try:
        url = ICON_SOURCES["simple-icons"]["index_url"]
        req = urllib.request.Request(url, headers={"User-Agent": "svg-animator/0.1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        # Simple Icons 格式：{"icons": [...]} 或直接是列表
        icons = data.get("icons", []) if isinstance(data, dict) else data
        query_lower = query.lower()

        matched = []
        for icon in icons:
            title = icon.get("title", "")
            # 从 title 生成 slug（转小写，移除特殊字符）
            slug = "".join(c.lower() if c.isalnum() else "" for c in title)
            # 检查 aliases
            aliases = icon.get("aliases", {})
            aka = [a.lower() for a in aliases.get("aka", [])]

            if query_lower in title.lower() or query_lower in slug or any(query_lower in a for a in aka):
                matched.append({
                    "id": f"simple-{slug}",
                    "name": title,
                    "source": "simple-icons",
                    "svg_url": f"{ICON_SOURCES['simple-icons']['base_url']}/{slug}.svg",
                    "color": f"#{icon.get('hex', '')}",
                    "license": "CC0-1.0",
                })
                if len(matched) >= limit:
                    break

        return matched
    except Exception as e:
        print(f"[icon_search] Simple Icons search failed: {e}")
        return []


def _search_iconfont(query: str, limit: int) -> list[dict[str, Any]]:
    """搜索 Iconfont（需要登录态，默认返回占位）。"""
    print(f"[icon_search] Iconfont search requested for: {query}")
    print("[icon_search] Iconfont requires authentication — returning placeholder")

    # 占位结果
    return [
        {
            "id": f"iconfont-{i}",
            "name": f"{query}_{i}",
            "source": "iconfont",
            "svg_path": "M10 10h80v80h-80z",
            "requires_auth": True,
        }
        for i in range(min(limit, 3))
    ]


def get_icon_svg(icon_id: str, source: str = "lucide") -> str:
    """获取指定图标的 SVG 内容。

    Args:
        icon_id: 图标 ID（不含前缀）
        source: 图标源

    Returns:
        SVG 字符串
    """
    if source == "lucide":
        url = f"{ICON_SOURCES['lucide']['base_url']}/{icon_id}.svg"
    elif source == "simple-icons":
        url = f"{ICON_SOURCES['simple-icons']['base_url']}/{icon_id}.svg"
    else:
        return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><!-- {source}:{icon_id} --></svg>"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "svg-animator/0.1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"[icon_search] Failed to fetch SVG: {e}")
        return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><!-- fetch failed: {icon_id} --></svg>"


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "home"
    source = sys.argv[2] if len(sys.argv) > 2 else "all"

    results = search_icons(query, source=source)
    print(json.dumps(results, indent=2, ensure_ascii=False))
