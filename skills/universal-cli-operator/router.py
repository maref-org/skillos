"""
universal-cli-operator router — 4-platform decision engine.

Routes automation tasks across:
  - Web:      agent-browser (CDP-based Chrome automation)
  - Social:   Agent-Reach / Platform Connectors
  - Desktop:  CLI-Anything (future)
  - Mobile:   Z Flip3 ADB Agent
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Platform(Enum):
    WEB = "web"
    SOCIAL = "social"
    DESKTOP = "desktop"
    MOBILE = "mobile"


@dataclass
class RouteDecision:
    platform: Platform
    confidence: float
    tool: str
    reason: str
    fallback_platform: Platform | None = None
    security_flags: list[str] = field(default_factory=list)
    requires_approval: bool = False


# Keyword → Platform mapping for routing decisions
KEYWORD_PLATFORM_MAP = {
    # Web keywords
    "http:": Platform.WEB, "https:": Platform.WEB,
    "url": Platform.WEB, "website": Platform.WEB, "page": Platform.WEB,
    "browser": Platform.WEB, "chrome": Platform.WEB, "login": Platform.WEB,
    "form": Platform.WEB, "download": Platform.WEB, "web": Platform.WEB,
    ".com": Platform.WEB, ".org": Platform.WEB, ".io": Platform.WEB,
    ".cn": Platform.WEB, ".net": Platform.WEB,

    # Social keywords
    "twitter": Platform.SOCIAL, "x.com": Platform.SOCIAL,
    "linkedin": Platform.SOCIAL, "instagram": Platform.SOCIAL,
    "facebook": Platform.SOCIAL, "discord": Platform.SOCIAL,
    "tiktok": Platform.SOCIAL, "youtube": Platform.SOCIAL,
    "bilibili": Platform.SOCIAL, "b站": Platform.SOCIAL,
    "小红书": Platform.SOCIAL, "微博": Platform.SOCIAL, "抖音": Platform.SOCIAL,
    "threads": Platform.SOCIAL, "即刻": Platform.SOCIAL,
    "post": Platform.SOCIAL, "tweet": Platform.SOCIAL,
    "publish": Platform.SOCIAL, "share": Platform.SOCIAL,
    "social": Platform.SOCIAL, "发布": Platform.SOCIAL,

    # Desktop keywords
    "file": Platform.DESKTOP, "folder": Platform.DESKTOP,
    "window": Platform.DESKTOP, "application": Platform.DESKTOP,
    "desktop": Platform.DESKTOP, "app": Platform.DESKTOP,
    "open file": Platform.DESKTOP, "save as": Platform.DESKTOP,
    "export": Platform.DESKTOP, "import": Platform.DESKTOP,

    # Mobile keywords
    "phone": Platform.MOBILE, "device": Platform.MOBILE,
    "mobile": Platform.MOBILE, "android": Platform.MOBILE,
    "z flip": Platform.MOBILE, "zflip": Platform.MOBILE,
    "samsung": Platform.MOBILE, "手机": Platform.MOBILE,
    "移动端": Platform.MOBILE, "mobile app": Platform.MOBILE,
}

# Domain whitelist for production mode
PRODUCTION_ALLOWED_DOMAINS = {
    "github.com", "x.com", "twitter.com", "linkedin.com",
    "youtube.com", "bilibili.com", "discord.com",
    "threads.net", "instagram.com", "xiaohongshu.com",
    "weibo.com", "douyin.com", "tiktok.com", "jike.com",
}

# Operations requiring HumanGate approval
SENSITIVE_OPERATIONS = {"eval", "download", "file_upload", "payment", "delete"}


class CLIOperatorRouter:
    def __init__(self, production_mode: bool = False,
                 allowed_domains: set | None = None):
        self.production_mode = production_mode
        self.allowed_domains = allowed_domains or PRODUCTION_ALLOWED_DOMAINS

    def route(self, target: str, action: str = "",
             platform_hint: str | None = None) -> RouteDecision:
        target_lower = target.lower()

        # If explicit platform hint given, use it
        if platform_hint:
            try:
                platform = Platform(platform_hint.lower())
                return RouteDecision(
                    platform=platform, confidence=1.0,
                    tool=self._tool_for_platform(platform),
                    reason=f"Explicit platform hint: {platform_hint}",
                )
            except ValueError:
                pass

        # Score each platform by keyword matches
        scores = dict.fromkeys(Platform, 0.0)
        for keyword, platform in KEYWORD_PLATFORM_MAP.items():
            if keyword.lower() in target_lower:
                scores[platform] += 1.0

        # Boost: URL pattern detection
        if re.search(r'https?://', target_lower):
            scores[Platform.WEB] += 3.0

        # Boost: social platform name exact match
        social_names = ["twitter", "x.com", "linkedin", "instagram", "facebook",
                       "discord", "tiktok", "youtube", "bilibili", "threads",
                       "小红书", "微博", "抖音", "即刻"]
        for name in social_names:
            if name.lower() in target_lower:
                scores[Platform.SOCIAL] += 2.0

        # Determine winner
        if max(scores.values()) == 0:
            # Default to SmartOrchestrator routing
            return RouteDecision(
                platform=Platform.WEB, confidence=0.3,
                tool="smart_orchestrator",
                reason="No keyword match; defaulting to SmartOrchestrator routing",
            )

        winner = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = scores[winner] / total if total > 0 else 0.0

        # Determine runner-up for fallback
        runner_up = None
        sorted_platforms = sorted(scores, key=scores.get, reverse=True)
        if len(sorted_platforms) > 1 and scores[sorted_platforms[1]] > 0:
            runner_up = sorted_platforms[1]

        decision = RouteDecision(
            platform=winner, confidence=round(confidence, 2),
            tool=self._tool_for_platform(winner),
            reason=f"Keyword match: {winner.value} (score={scores[winner]})",
            fallback_platform=runner_up,
        )

        # Security checks
        decision.security_flags = self._security_check(target, action, winner)
        decision.requires_approval = any(
            op in target_lower or op in action.lower()
            for op in SENSITIVE_OPERATIONS
        )

        return decision

    def _tool_for_platform(self, platform: Platform) -> str:
        return {
            Platform.WEB: "agent-browser",
            Platform.SOCIAL: "Agent-Reach / Platform Connectors",
            Platform.DESKTOP: "CLI-Anything (future)",
            Platform.MOBILE: "Z Flip3 Agent (ADB)",
        }[platform]

    def _security_check(self, target: str, action: str,
                       platform: Platform) -> list[str]:
        flags = []

        # Domain check for web operations
        if platform == Platform.WEB:
            domain = self._extract_domain(target)
            if domain and self.production_mode:
                if not any(domain.endswith(d) for d in self.allowed_domains):
                    flags.append(f"domain_not_whitelisted:{domain}")

        # Rate limit check for social
        if platform == Platform.SOCIAL and "publish" in action.lower():
            flags.append("social_rate_limit: max 3 posts/hour/platform")

        # ADB connection check for mobile
        if platform == Platform.MOBILE:
            flags.append("adb_connection_required")

        return flags

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        match = re.search(r'https?://([^/\s"\'<>]+)', url)
        return match.group(1).lower() if match else None


def route_task(target: str, action: str = "",
              platform_hint: str | None = None,
              production_mode: bool = False) -> RouteDecision:
    router = CLIOperatorRouter(production_mode=production_mode)
    return router.route(target, action, platform_hint)


def get_platform_for_keywords(text: str) -> list[Platform]:
    matches = set()
    text_lower = text.lower()
    for keyword, platform in KEYWORD_PLATFORM_MAP.items():
        if keyword.lower() in text_lower:
            matches.add(platform)
    return list(matches) if matches else [Platform.WEB]
