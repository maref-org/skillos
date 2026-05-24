"""universal-cli-operator skill — 4-platform CLI routing engine."""

from .router import (
    KEYWORD_PLATFORM_MAP,
    CLIOperatorRouter,
    Platform,
    RouteDecision,
    get_platform_for_keywords,
    route_task,
)

__all__ = [
    "CLIOperatorRouter",
    "Platform",
    "RouteDecision",
    "route_task",
    "get_platform_for_keywords",
    "KEYWORD_PLATFORM_MAP",
]
