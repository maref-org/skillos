#!/usr/bin/env python3
"""SVG Animator Harness — SVG安全扫描 + 视觉校验层。

独立于 opendesign-skill 的校验规则，专为 SVG/动画设计。
支持无头浏览器渲染校验（Playwright）。
"""

import re
from pathlib import Path
from typing import Any

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class SVGHarness:
    """SVG 安全与质量校验。"""

    MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
    MAX_DURATION_SECONDS = 10

    def validate(self, content: str) -> tuple[bool, list[str]]:
        """校验 SVG/HTML 动画内容。

        Returns:
            (is_valid, errors)
        """
        errors: list[str] = []

        # 1. 大小检查
        if len(content.encode()) > self.MAX_SIZE_BYTES:
            errors.append(f"SVG size ({len(content)} bytes) exceeds {self.MAX_SIZE_BYTES} limit")

        # 2. 安全检查
        errors.extend(self._security_check(content))

        # 3. 格式检查
        errors.extend(self._format_check(content))

        # 4. 动画检查
        errors.extend(self._animation_check(content))

        return len(errors) == 0, errors

    async def validate_with_browser(self, html_content: str, output_dir: str = "output") -> dict[str, Any]:
        """使用无头浏览器进行视觉校验。

        Args:
            html_content: HTML 内容
            output_dir: 输出目录

        Returns:
            校验结果字典
        """
        if not HAS_PLAYWRIGHT:
            return {"status": "skipped", "reason": "Playwright not available"}

        result = {
            "status": "success",
            "screenshot": None,
            "console_errors": [],
            "animation_detected": False,
            "frame_rate": None,
        }

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # 收集控制台错误
                console_errors = []
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

                # 写入临时文件并加载
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                temp_html = output_path / "_validate_temp.html"
                temp_html.write_text(html_content)

                await page.goto(f"file://{temp_html.resolve()}", wait_until="networkidle")

                # 截图
                screenshot_path = output_path / "validation_screenshot.png"
                await page.screenshot(path=str(screenshot_path))
                result["screenshot"] = str(screenshot_path)

                # 检查是否有动画
                has_animation = await page.evaluate("""() => {
                    const styles = document.styleSheets;
                    for (let sheet of styles) {
                        try {
                            for (let rule of sheet.cssRules) {
                                if (rule.cssText.includes('@keyframes') || rule.cssText.includes('animation')) {
                                    return true;
                                }
                            }
                        } catch (e) {}
                    }
                    return false;
                }""")
                result["animation_detected"] = has_animation

                # 收集控制台错误
                result["console_errors"] = console_errors

                await browser.close()

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _security_check(self, content: str) -> list[str]:
        """SVG 安全扫描 — 移除危险元素。"""
        errors = []

        # 检测 <script> 标签
        if re.search(r'<script\b', content, re.IGNORECASE):
            errors.append("SECURITY: Contains <script> tag — must be removed")

        # 检测 on* 事件属性
        if re.search(r'\bon\w+\s*=', content, re.IGNORECASE):
            errors.append("SECURITY: Contains event handler (on*) — must be removed")

        # 检测 javascript: URL
        if re.search(r'javascript:', content, re.IGNORECASE):
            errors.append("SECURITY: Contains javascript: URL — must be removed")

        return errors

    def _format_check(self, content: str) -> list[str]:
        """SVG 格式校验。"""
        errors = []

        # 检查 xmlns 声明
        if 'xmlns="http://www.w3.org/2000/svg"' not in content:
            errors.append("FORMAT: Missing xmlns declaration for SVG namespace")

        # 检查 viewBox
        if 'viewBox' not in content and 'width' not in content:
            errors.append("FORMAT: Missing viewBox or width/height attributes")

        return errors

    def _animation_check(self, content: str) -> list[str]:
        """动画质量检查。"""
        errors = []

        # 检查是否包含动画定义
        has_css_animation = '@keyframes' in content or 'animation:' in content
        has_smil_animation = '<animate' in content or '<animateTransform' in content

        if not has_css_animation and not has_smil_animation:
            errors.append("ANIMATION: No animation found (expected @keyframes or <animate>)")

        # 检查动画时长是否超限
        duration_match = re.search(r'animation:\s*\w+\s+([\d.]+)s', content)
        if duration_match:
            duration = float(duration_match.group(1))
            if duration > self.MAX_DURATION_SECONDS:
                errors.append(f"ANIMATION: Duration ({duration}s) exceeds {self.MAX_DURATION_SECONDS}s limit")

        return errors

    def sanitize(self, content: str) -> str:
        """清理 SVG 内容（移除危险元素）。"""
        # 移除 <script> 标签
        content = re.sub(r'<script\b[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)

        # 移除 on* 事件属性
        content = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)

        # 移除 javascript: URL
        content = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', '', content, flags=re.IGNORECASE)

        return content


def validate_animation(content: str) -> tuple[bool, list[str]]:
    """便捷函数：校验动画内容。"""
    harness = SVGHarness()
    return harness.validate(content)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python harness.py <svg_file>")
        sys.exit(1)

    svg_path = Path(sys.argv[1])
    content = svg_path.read_text()

    valid, errors = validate_animation(content)
    if valid:
        print("✅ SVG validation passed")
    else:
        print("❌ SVG validation failed:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
