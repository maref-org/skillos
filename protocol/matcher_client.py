#!/usr/bin/env python3
"""Matcher Client — 意图-技能撮合引擎协议客户端

职责：
  - 根据用户意图匹配最合适的 Skill
  - 多候选排序（基于评分、价格、延迟）
  - 推荐反馈学习
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@dataclass
class MatchRequest:
    user_intent: str
    user_id: str
    context: dict[str, Any] = field(default_factory=dict)
    max_results: int = 5
    budget_limit_usd: float | None = None


@dataclass
class MatchCandidate:
    skill_id: str
    skill_name: str
    score: float
    price_per_call: float
    avg_latency_ms: float
    success_rate: float
    author: str


@dataclass
class MatchResult:
    request_id: str
    candidates: list[MatchCandidate]
    best_match: MatchCandidate | None
    match_time_ms: float
    total_available: int


class MatcherClient:
    """撮合引擎客户端"""

    def __init__(self, base_url: str = "http://localhost:8080", api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key
        self._match_history: list[MatchResult] = []

    def match(self, request: MatchRequest) -> MatchResult:
        """根据意图匹配技能"""
        start = time.monotonic()

        payload = {
            "jsonrpc": "2.0",
            "method": "matcher.match",
            "params": {
                "user_intent": request.user_intent,
                "user_id": request.user_id,
                "context": request.context,
                "max_results": request.max_results,
                "budget_limit": request.budget_limit_usd,
            },
            "id": 1,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

            candidates = [
                MatchCandidate(
                    skill_id=c["skill_id"],
                    skill_name=c["skill_name"],
                    score=c["score"],
                    price_per_call=c.get("price_per_call", 0.0),
                    avg_latency_ms=c.get("avg_latency_ms", 500.0),
                    success_rate=c.get("success_rate", 1.0),
                    author=c.get("author", "anonymous"),
                )
                for c in data.get("result", {}).get("candidates", [])
            ]

            best = candidates[0] if candidates else None

            match_time_ms = (time.monotonic() - start) * 1000

            result = MatchResult(
                request_id=str(data.get("id", 1)),
                candidates=candidates,
                best_match=best,
                match_time_ms=round(match_time_ms, 2),
                total_available=data.get("result", {}).get("total_available", 0),
            )

            self._match_history.append(result)
            return result

        except requests.RequestException as e:
            logger.warning("Matcher request failed: %s", e)
            return MatchResult(
                request_id="local",
                candidates=[],
                best_match=None,
                match_time_ms=round((time.monotonic() - start) * 1000, 2),
                total_available=0,
            )

    def report_outcome(self, skill_id: str, success: bool, rating: float = 0.0) -> bool:
        """反馈匹配结果，用于优化推荐"""
        payload = {
            "jsonrpc": "2.0",
            "method": "matcher.feedback",
            "params": {
                "skill_id": skill_id,
                "success": success,
                "rating": rating,
            },
            "id": 2,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=5.0,
            )
            status_ok: bool = resp.status_code == 200
            return status_ok
        except requests.RequestException as e:
            logger.warning("Matcher feedback failed: %s", e)
            return False

    def get_match_history(self) -> list[MatchResult]:
        return list(self._match_history)

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
