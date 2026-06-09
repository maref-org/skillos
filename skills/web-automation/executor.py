"""
web-automation executor — Python async wrapper around agent-browser CLI.

All functions invoke `agent-browser` subprocess with structured output (--json).
Session management is handled transparently by agent-browser.
"""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

AGENT_BROWSER_BIN = "agent-browser"


def is_agent_browser_installed() -> bool:
    return shutil.which(AGENT_BROWSER_BIN) is not None


def get_install_hint() -> str:
    return "npm install -g agent-browser && agent-browser install"


@dataclass
class BrowserResult:
    success: bool
    action: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SnapshotElement:
    ref: str
    tag: str
    text: str = ""
    attrs: dict[str, str] = field(default_factory=dict)


class WebAutomationExecutor:
    def __init__(self, timeout: int = 30, verbose: bool = False):
        self.timeout = timeout
        self.verbose = verbose
        self._verify_install()

    def _verify_install(self):
        if not is_agent_browser_installed():
            hint = get_install_hint()
            logger.warning(f"agent-browser not found. Install: {hint}")

    async def _run(self, *args: str) -> BrowserResult:
        cmd = [AGENT_BROWSER_BIN, *args]
        if self.verbose:
            logger.info(f"agent-browser: {' '.join(args)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                return BrowserResult(success=False, action=args[0], error=stderr_text or f"exit code {proc.returncode}")

            data = {}
            try:
                data = json.loads(stdout_text) if stdout_text else {}
            except json.JSONDecodeError:
                data = {"raw": stdout_text}

            return BrowserResult(success=True, action=args[0], data=data)

        except TimeoutError:
            return BrowserResult(success=False, action=args[0], error="Command timed out")
        except FileNotFoundError:
            return BrowserResult(success=False, action=args[0], error=f"agent-browser not found. {get_install_hint()}")
        except Exception as e:
            return BrowserResult(success=False, action=args[0], error=str(e))

    async def doctor(self) -> BrowserResult:
        result = await self._run("doctor", "--json")
        if result.success and result.data:
            checks = result.data
            failed = [c for c in checks if not c.get("passed", False)] if isinstance(checks, list) else []
            if failed:
                result.success = False
                result.error = f"{len(failed)} checks failed: {[c.get('name') for c in failed]}"
        return result

    async def navigate(self, url: str) -> BrowserResult:
        return await self._run("open", url)

    async def snapshot(self, interactive_only: bool = True) -> BrowserResult:
        args = ["snapshot", "--json"]
        if interactive_only:
            args.append("-i")
        result = await self._run(*args)
        if result.success and "elements" in result.data:
            elements = [SnapshotElement(**e) for e in result.data.get("elements", [])]
            result.data["parsed_elements"] = elements
        return result

    async def click(self, ref: str) -> BrowserResult:
        return await self._run("click", ref)

    async def fill(self, ref: str, value: str) -> BrowserResult:
        return await self._run("fill", ref, value)

    async def submit(self) -> BrowserResult:
        return await self._run("submit")

    async def screenshot(
        self, output_path: str | None = None, full_page: bool = False, annotate: bool = False
    ) -> BrowserResult:
        args = ["screenshot"]
        if full_page:
            args.append("--full")
        if annotate:
            args.append("--annotate")
        if output_path:
            args.extend(["--output", output_path])
        return await self._run(*args)

    async def extract(self, selector: str) -> BrowserResult:
        return await self._run("get", "text", selector)

    async def get_title(self) -> BrowserResult:
        return await self._run("get", "title")

    async def press_key(self, key: str) -> BrowserResult:
        return await self._run("press", key)

    async def scroll(self, direction: str) -> BrowserResult:
        return await self._run("scroll", direction)

    async def evaluate(self, js: str) -> BrowserResult:
        return await self._run("eval", js)

    async def close(self) -> BrowserResult:
        return await self._run("close")

    async def run_batch(self, commands: list[dict[str, Any]]) -> list[BrowserResult]:
        results = []
        for cmd in commands:
            action = cmd.get("action", "")
            args = cmd.get("args", [])
            if isinstance(args, str):
                args = [args]
            result = await self._run(action, *args)
            results.append(result)
            if not result.success and action != "close":
                logger.warning(f"Batch command '{action}' failed: {result.error}")
        return results


# Module-level convenience functions
_executor: WebAutomationExecutor | None = None


def _get_executor() -> WebAutomationExecutor:
    global _executor
    if _executor is None:
        _executor = WebAutomationExecutor()
    return _executor


async def browser_doctor() -> BrowserResult:
    return await _get_executor().doctor()


async def browser_navigate(url: str) -> BrowserResult:
    return await _get_executor().navigate(url)


async def browser_snapshot(interactive_only: bool = True) -> BrowserResult:
    return await _get_executor().snapshot(interactive_only)


async def browser_click(ref: str) -> BrowserResult:
    return await _get_executor().click(ref)


async def browser_fill(ref: str, value: str) -> BrowserResult:
    return await _get_executor().fill(ref, value)


async def browser_submit() -> BrowserResult:
    return await _get_executor().submit()


async def browser_screenshot(
    output_path: str | None = None, full_page: bool = False, annotate: bool = False
) -> BrowserResult:
    return await _get_executor().screenshot(output_path, full_page, annotate)


async def browser_extract(selector: str) -> BrowserResult:
    return await _get_executor().extract(selector)


async def browser_close() -> BrowserResult:
    global _executor
    result = await _get_executor().close()
    _executor = None
    return result


async def browser_run_batch(commands: list[dict[str, Any]]) -> list[BrowserResult]:
    return await _get_executor().run_batch(commands)
