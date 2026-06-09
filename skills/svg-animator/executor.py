#!/usr/bin/env python3
"""SVG Animator Executor — ReAct 循环执行引擎。

独立原子能力，不依赖 opendesign-skill。
通过 context 参数接收上游传递的 VI 结果摘要。
支持 LLM 驱动的动画生成。
"""

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

# 本地模块
from harness import SVGHarness
from tools.iconfont_search import search_icons
from tools.lottie_exporter import export_lottie
from tools.svg_parser import parse_svg


class SVGAnimator:
    """ReAct 循环：观察 → 思考 → 行动 → 校验 → 输出。"""

    def __init__(
        self,
        prompt: str,
        context: dict | None = None,
        output_format: str = "html",
        llm_api_url: str | None = None,
    ):
        self.prompt = prompt
        self.context = context or {}
        self.output_format = output_format
        self.harness = SVGHarness()
        self.max_retries = 3
        self.llm_api_url = llm_api_url or os.environ.get("LLM_API_URL")

    def run(self) -> dict[str, Any]:
        """执行主循环。"""
        # Step 1: 获取/生成基础 SVG
        svg_input = self._resolve_svg_input()

        # Step 2: 解析 SVG
        parsed = parse_svg(svg_input)

        # Step 3: 生成动画
        animation = self._generate_animation(parsed)

        # Step 4: Harness 校验循环
        valid = False
        errors = []
        for attempt in range(self.max_retries):
            valid, errors = self.harness.validate(animation)
            if valid:
                break
            print(f"[harness] Attempt {attempt + 1} failed: {errors}")
            animation = self._regenerate(animation, errors)

        # Step 5: 导出
        output_path = self._export(animation)

        # Step 6: 浏览器视觉校验（可选）
        browser_result = {"status": "skipped"}
        if self.context.get("browser_validate", False):
            browser_result = asyncio.run(self.harness.validate_with_browser(animation))

        return {
            "status": "success" if valid else "partial",
            "output_path": str(output_path),
            "format": self.output_format,
            "validation": {"passed": valid, "errors": errors if not valid else []},
            "browser_validation": browser_result,
        }

    def _resolve_svg_input(self) -> str:
        """解析 SVG 输入来源。"""
        # 优先级：context 传入 > 图标搜索 > 生成基础 SVG
        if "svg_content" in self.context:
            return self.context["svg_content"]

        if "svg_file" in self.context:
            return Path(self.context["svg_file"]).read_text()

        # 尝试从图标库搜索
        icon_query = self.context.get("icon_query")
        if icon_query:
            icons = search_icons(icon_query, limit=1, source=self.context.get("icon_source", "all"))
            if icons:
                icon = icons[0]
                icon["source"]
                # 从 svg_url 获取 SVG 内容
                try:
                    svg_url = icon.get("svg_url")
                    if svg_url:
                        req = urllib.request.Request(svg_url, headers={"User-Agent": "svg-animator/0.1.0"})
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            return resp.read().decode("utf-8")
                except Exception as e:
                    print(f"[executor] Failed to fetch SVG from URL: {e}")

        # 默认：生成基础 SVG
        return self._generate_base_svg()

    def _generate_base_svg(self) -> str:
        """生成基础占位 SVG。"""
        brand = self.context.get("brand_name", "Logo")
        color = self.context.get("color_primary", "#0071e3")
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" stroke="{color}" stroke-width="2" fill="none"/>
  <text x="50" y="55" text-anchor="middle" font-size="14" fill="{color}">{brand[0]}</text>
</svg>"""

    def _generate_animation(self, svg_data: dict) -> str:
        """生成动画。

        策略：
        1. 如果有 LLM API，调用 LLM 生成定制动画
        2. 否则使用内置模板引擎
        """
        if self.llm_api_url:
            return self._generate_with_llm(svg_data)
        return self._generate_with_template(svg_data)

    def _generate_with_llm(self, svg_data: dict) -> str:
        """通过 LLM 生成动画（需要配置 LLM_API_URL）。"""
        system_prompt = """你是一个 SVG 动画专家。根据用户需求和 SVG 内容，生成完整的 HTML 动画文件。

要求：
1. 输出完整的 HTML 文件（包含 <style> 和 <script>）
2. 使用 CSS @keyframes 动画（优先于 SMIL）
3. 使用 CSS 变量管理颜色
4. 动画时长 2-3 秒，easing 使用 ease-in-out
5. 确保 SVG 包含 xmlns 声明
6. 不要包含任何 JavaScript 事件处理器（安全要求）"""

        user_prompt = f"""需求：{self.prompt}

SVG 内容：
```svg
{svg_data.get("raw", "")[:2000]}
```

上下文：
{json.dumps(self.context, ensure_ascii=False)}

请输出完整的 HTML 文件代码。"""

        try:
            body = json.dumps(
                {
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4000,
                }
            ).encode()

            req = urllib.request.Request(
                self.llm_api_url,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())

            content = result["choices"][0]["message"]["content"]
            # 提取代码块
            if "```html" in content:
                start = content.index("```html") + 7
                end = content.index("```", start)
                return content[start:end].strip()
            return content
        except Exception as e:
            print(f"[executor] LLM generation failed: {e}, falling back to template")
            return self._generate_with_template(svg_data)

    def _generate_with_template(self, svg_data: dict) -> str:
        """使用内置模板引擎生成动画。"""
        anim_type = self.context.get("animation_type", "draw")
        duration = self.context.get("duration", 2.0)
        easing = self.context.get("easing", "ease-in-out")
        colors = self.context.get(
            "colors",
            {
                "primary": self.context.get("color_primary", "#0071e3"),
                "secondary": self.context.get("color_secondary", "#2f7d4a"),
            },
        )

        svg_raw = svg_data.get("raw", "")
        css = self._build_css(anim_type, duration, easing, colors)

        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SVG Animation — {anim_type}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  display: flex; justify-content: center; align-items: center;
  min-height: 100vh; background: #f5f5f7; font-family: -apple-system, sans-serif;
}}
.container {{ width: 400px; height: 400px; display: flex; justify-content: center; align-items: center; }}
{css}
</style>
</head>
<body>
<div class="container">
  {svg_raw}
</div>
</body>
</html>"""
        return html

    def _build_css(self, anim_type: str, duration: float, easing: str, colors: dict) -> str:
        """构建 CSS 动画关键帧。"""
        primary = colors.get("primary", "#0071e3")
        secondary = colors.get("secondary", "#2f7d4a")

        animations = {
            "draw": f"""
@keyframes draw {{
  from {{ stroke-dashoffset: 1000; }}
  to {{ stroke-dashoffset: 0; }}
}}
svg path, svg circle, svg rect {{
  stroke-dasharray: 1000;
  animation: draw {duration}s {easing} forwards;
  stroke: {primary};
  fill: none;
}}""",
            "fade": f"""
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
svg {{ animation: fadeIn {duration}s {easing} forwards; }}""",
            "scale": f"""
@keyframes scaleBounce {{
  0% {{ transform: scale(0) rotate(-10deg); }}
  60% {{ transform: scale(1.1) rotate(2deg); }}
  100% {{ transform: scale(1) rotate(0deg); }}
}}
svg {{ animation: scaleBounce {duration}s {easing} forwards; }}""",
            "rotate": f"""
@keyframes rotateIn {{
  from {{ transform: rotate(-180deg) scale(0); opacity: 0; }}
  to {{ transform: rotate(0deg) scale(1); opacity: 1; }}
}}
svg {{ animation: rotateIn {duration}s {easing} forwards; }}""",
            "color_shift": f"""
@keyframes colorShift {{
  0% {{ stroke: {primary}; fill: transparent; }}
  50% {{ stroke: {secondary}; fill: {primary}22; }}
  100% {{ stroke: {primary}; fill: {primary}11; }}
}}
svg path, svg circle {{
  animation: colorShift {duration}s {easing} infinite alternate;
  stroke-width: 2;
}}""",
            "morph": f"""
@keyframes morph {{
  0% {{ d: path("M50 10 L90 50 L50 90 L10 50 Z"); }}
  50% {{ d: path("M50 5 C75 5 95 25 95 50 C95 75 75 95 50 95 C25 95 5 75 5 50 C5 25 25 5 50 5 Z"); }}
  100% {{ d: path("M50 10 L90 50 L50 90 L10 50 Z"); }}
}}
svg path {{ animation: morph {duration}s {easing} infinite; }}""",
        }

        return animations.get(anim_type, animations["draw"])

    def _regenerate(self, animation: str, errors: list[str]) -> str:
        """根据校验错误重新生成。"""
        print(f"[executor] Regenerating to fix: {errors}")

        # 简单修复策略
        fixed = animation
        for err in errors:
            if "xmlns" in err and "xmlns=" not in fixed:
                fixed = fixed.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
            if "script" in err.lower():
                import re

                fixed = re.sub(r"<script\b[^>]*>.*?</script>", "", fixed, flags=re.IGNORECASE | re.DOTALL)
            if "on*" in err or "event handler" in err.lower():
                import re

                fixed = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', "", fixed, flags=re.IGNORECASE)

        return fixed

    def _export(self, animation: str) -> Path:
        """导出动画到文件。"""
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        if self.output_format == "lottie":
            output_path = output_dir / "animation.json"
            export_lottie(animation, output_path)
        elif self.output_format == "svg":
            output_path = output_dir / "animation.svg"
            # 提取 SVG 部分
            import re

            svg_match = re.search(r"<svg[^>]*>.*?</svg>", animation, re.DOTALL)
            if svg_match:
                output_path.write_text(svg_match.group())
            else:
                output_path.write_text(animation)
        else:
            output_path = output_dir / "animation.html"
            output_path.write_text(animation)

        return output_path


def main():
    parser = argparse.ArgumentParser(description="SVG Animator Executor")
    parser.add_argument("--prompt", required=True, help="动画生成提示词")
    parser.add_argument("--context", default="{}", help="JSON 格式上下文")
    parser.add_argument("--format", choices=["html", "svg", "lottie"], default="html")
    parser.add_argument("--input", help="输入 SVG 文件路径")
    parser.add_argument("--llm-api", help="LLM API URL (可选)")
    args = parser.parse_args()

    context = json.loads(args.context)
    if args.input:
        context["svg_file"] = args.input

    animator = SVGAnimator(
        prompt=args.prompt,
        context=context,
        output_format=args.format,
        llm_api_url=args.llm_api,
    )
    result = animator.run()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
