#!/usr/bin/env python3
"""Matcher Client — 意图-技能撮合引擎协议客户端

职责：
  - 根据用户意图匹配最合适的 Skill
  - 多候选排序（基于评分、价格、延迟）
  - 推荐反馈学习

安全：强制 HTTPS，指数退避重试，熔断保护
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests  # type: ignore[import-untyped]

from skillos.observability.metrics import get_metrics
from skillos.security.message_signer import get_default_signer

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
    """撮合引擎客户端 — 安全增强版"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ):
        raw_url = base_url or os.getenv("SKILLOS_MATCHER_URL", "https://localhost:8080")
        self.base_url = self._enforce_https(raw_url)  # type: ignore[arg-type]
        self._api_key = api_key or os.getenv("SKILLOS_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._match_history: list[MatchResult] = []
        # 简单熔断器状态
        self._circuit_failures = 0
        self._circuit_last_failure = 0.0
        self._circuit_threshold = 5
        self._circuit_timeout = 60.0

    @staticmethod
    def _enforce_https(url: str) -> str:
        """强制使用 HTTPS，禁止明文 HTTP 传输"""
        if url.startswith("http://"):
            if os.getenv("SKILLOS_INSECURE", "0") == "1":
                logger.warning("Insecure HTTP enabled via SKILLOS_INSECURE=1")
                return url
            raise ValueError(
                "HTTP is not allowed in production. Use HTTPS or set SKILLOS_INSECURE=1 for development only."
            )
        if not url.startswith("https://"):
            return f"https://{url}"
        return url

    def _is_circuit_open(self) -> bool:
        """检查熔断器是否打开"""
        if self._circuit_failures < self._circuit_threshold:
            return False
        if time.time() - self._circuit_last_failure > self._circuit_timeout:
            self._circuit_failures = 0
            return False
        return True

    def _record_failure(self) -> None:
        """记录请求失败"""
        self._circuit_failures += 1
        self._circuit_last_failure = time.time()

    def _record_success(self) -> None:
        """记录请求成功"""
        if self._circuit_failures > 0:
            self._circuit_failures = 0

    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        """带指数退避重试的请求"""
        if self._is_circuit_open():
            raise requests.RequestException("Circuit breaker is open")

        # 自动签名 JSON payload（若 MessageSigner 已配置）
        json_payload = kwargs.get("json")
        if json_payload is not None:
            signer = get_default_signer()
            if signer is not None:
                headers = kwargs.get("headers") or {}
                headers.update(signer.sign_headers_http(json_payload))
                kwargs["headers"] = headers

        last_exception: Exception | None = None
        from urllib.parse import urlparse

        endpoint = urlparse(url).path or url
        for attempt in range(self.max_retries):
            start = time.monotonic()
            try:
                resp = requests.request(method, url, **kwargs)
                duration = time.monotonic() - start
                get_metrics().record_request(endpoint, resp.status_code, duration)
                self._record_success()
                return resp
            except requests.RequestException as exc:
                duration = time.monotonic() - start
                get_metrics().record_request(endpoint, 0, duration)
                get_metrics().record_error(type(exc).__name__)
                last_exception = exc
                self._record_failure()
                wait = self.retry_backoff * (2**attempt)
                logger.warning(
                    "Request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    self.max_retries,
                    wait,
                    exc,
                )
                time.sleep(wait)

        raise last_exception or requests.RequestException("All retries exhausted")

    def match(self, request: MatchRequest) -> MatchResult:
        """根据意图匹配技能"""
        if not request.user_intent or not isinstance(request.user_intent, str):
            raise ValueError("user_intent must be a non-empty string")
        if not request.user_id or not isinstance(request.user_id, str):
            raise ValueError("user_id must be a non-empty string")
        if request.max_results < 1 or request.max_results > 100:
            raise ValueError("max_results must be between 1 and 100")

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
            resp = self._request_with_retry(
                "POST",
                f"{self.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=self.timeout,
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
        if not skill_id or not isinstance(skill_id, str):
            raise ValueError("skill_id must be a non-empty string")

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
            resp = self._request_with_retry(
                "POST",
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
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
