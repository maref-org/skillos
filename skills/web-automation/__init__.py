"""web-automation skill — Browser automation via agent-browser CLI."""

from .executor import (
    WebAutomationExecutor,
    browser_click,
    browser_close,
    browser_doctor,
    browser_extract,
    browser_fill,
    browser_navigate,
    browser_run_batch,
    browser_screenshot,
    browser_snapshot,
    browser_submit,
    get_install_hint,
    is_agent_browser_installed,
)

__all__ = [
    "WebAutomationExecutor",
    "browser_navigate", "browser_snapshot", "browser_click",
    "browser_fill", "browser_submit", "browser_screenshot",
    "browser_extract", "browser_close", "browser_doctor",
    "browser_run_batch",
    "is_agent_browser_installed", "get_install_hint",
]
