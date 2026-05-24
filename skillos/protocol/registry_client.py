#!/usr/bin/env python3
"""Skill Registry Client — 技能注册中心协议客户端

职责：
  - 技能发现与搜索
  - 技能注册与发布
  - 技能版本管理
  - 技能元数据缓存

协议：JSON-RPC 2.0 + SSE
安全：强制 HTTPS，指数退避重试，熔断保护
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import requests  # type: ignore[import-untyped]

from skillos.types import SkillManifest, SkillStatus

logger = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    base_url: str = "https://localhost:8080"
    timeout: float = 10.0
    cache_ttl: float = 300.0
    max_retries: int = 3
    retry_backoff: float = 1.0  # 指数退避基数（秒）


@dataclass
class SearchResult:
    skills: list[SkillManifest]
    total: int
    page: int
    per_page: int


class RegistryClient:
    """技能注册中心客户端 — 安全增强版"""

    def __init__(self, config: RegistryConfig | None = None):
        self.config = config or RegistryConfig()
        # 强制 HTTPS
        self.config.base_url = self._enforce_https(self.config.base_url)
        # API Key 从环境变量读取，禁止明文存储于配置对象
        self._api_key = os.getenv("SKILLOS_API_KEY")
        self._cache: dict[str, tuple[SkillManifest, float]] = {}
        # 简单熔断器状态
        self._circuit_failures = 0
        self._circuit_last_failure = 0.0
        self._circuit_threshold = 5  # 连续失败 5 次熔断
        self._circuit_timeout = 60.0  # 熔断后 60 秒尝试恢复

    @staticmethod
    def _enforce_https(url: str) -> str:
        """强制使用 HTTPS，禁止明文 HTTP 传输"""
        if url.startswith("http://"):
            if os.getenv("SKILLOS_INSECURE", "0") == "1":
                logger.warning("Insecure HTTP enabled via SKILLOS_INSECURE=1")
                return url
            raise ValueError(
                "HTTP is not allowed in production. "
                "Use HTTPS or set SKILLOS_INSECURE=1 for development only."
            )
        if not url.startswith("https://"):
            return f"https://{url}"
        return url

    def _is_circuit_open(self) -> bool:
        """检查熔断器是否打开"""
        if self._circuit_failures < self._circuit_threshold:
            return False
        if time.time() - self._circuit_last_failure > self._circuit_timeout:
            # 尝试恢复：重置失败计数
            self._circuit_failures = 0
            return False
        return True

    def _record_failure(self) -> None:
        """记录请求失败"""
        self._circuit_failures += 1
        self._circuit_last_failure = time.time()

    def _record_success(self) -> None:
        """记录请求成功，重置失败计数"""
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

        last_exception: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                resp = requests.request(method, url, **kwargs)
                self._record_success()
                return resp
            except requests.RequestException as exc:
                last_exception = exc
                self._record_failure()
                wait = self.config.retry_backoff * (2 ** attempt)
                logger.warning(
                    "Request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    self.config.max_retries,
                    wait,
                    exc,
                )
                time.sleep(wait)

        raise last_exception or requests.RequestException("All retries exhausted")

    def register(self, manifest: SkillManifest) -> str:
        """注册新技能"""
        if not manifest.id or not isinstance(manifest.id, str):
            raise ValueError("manifest.id must be a non-empty string")
        if not manifest.name or not isinstance(manifest.name, str):
            raise ValueError("manifest.name must be a non-empty string")

        payload = {
            "jsonrpc": "2.0",
            "method": "skill.register",
            "params": {
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "author": manifest.author,
                "description": manifest.description,
                "license": manifest.license_type,
                "entry_point": manifest.entry_point,
                "dependencies": manifest.dependencies,
                "price_per_call": manifest.price_per_call,
                "metadata": manifest.metadata,
            },
            "id": 1,
        }

        try:
            resp = self._request_with_retry(
                "POST",
                f"{self.config.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            result = resp.json()
            skill_id: str = result.get("result", {}).get("id", manifest.id)
            logger.info("Skill registered: %s", skill_id)
            return skill_id
        except requests.RequestException as e:
            logger.warning("Registry registration failed, using local fallback: %s", e)
            self._cache[manifest.id] = (manifest, time.time())
            return manifest.id

    def get_skill(self, skill_id: str, version: str | None = None) -> SkillManifest | None:
        """获取技能元数据"""
        if not skill_id or not isinstance(skill_id, str):
            raise ValueError("skill_id must be a non-empty string")

        cache_key = f"{skill_id}:{version}" if version else skill_id

        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[1]) < self.config.cache_ttl:
            return cached[0]

        try:
            params = {"version": version} if version else {}
            resp = self._request_with_retry(
                "GET",
                f"{self.config.base_url}/api/v1/skills/{skill_id}",
                params=params,
                headers=self._auth_headers(),
                timeout=self.config.timeout,
            )

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            data = resp.json()
            manifest = self._parse_manifest(data)
            self._cache[cache_key] = (manifest, time.time())
            return manifest
        except requests.RequestException as e:
            logger.warning("Registry fetch failed for %s: %s", skill_id, e)
            return None

    def search(
        self,
        query: str,
        author: str | None = None,
        status: SkillStatus | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> SearchResult:
        """搜索技能"""
        if not query or not isinstance(query, str):
            raise ValueError("query must be a non-empty string")
        if page < 1:
            raise ValueError("page must be >= 1")
        if per_page < 1 or per_page > 100:
            raise ValueError("per_page must be between 1 and 100")

        params: dict[str, Any] = {
            "q": query,
            "page": page,
            "per_page": per_page,
        }
        if author:
            params["author"] = author
        if status:
            params["status"] = status.value

        try:
            resp = self._request_with_retry(
                "GET",
                f"{self.config.base_url}/api/v1/skills",
                params=params,
                headers=self._auth_headers(),
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            skills = [self._parse_manifest(s) for s in data.get("items", [])]
            return SearchResult(
                skills=skills,
                total=data.get("total", 0),
                page=data.get("page", page),
                per_page=data.get("per_page", per_page),
            )
        except requests.RequestException as e:
            logger.warning("Registry search failed: %s", e)
            return SearchResult(skills=[], total=0, page=page, per_page=per_page)

    def publish(self, skill_id: str, version: str) -> bool:
        """发布技能（DRAFT → PUBLISHED）"""
        if not skill_id or not isinstance(skill_id, str):
            raise ValueError("skill_id must be a non-empty string")
        if not version or not isinstance(version, str):
            raise ValueError("version must be a non-empty string")

        payload = {
            "jsonrpc": "2.0",
            "method": "skill.publish",
            "params": {"id": skill_id, "version": version},
            "id": 2,
        }

        try:
            resp = self._request_with_retry(
                "POST",
                f"{self.config.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            logger.info("Skill published: %s v%s", skill_id, version)
            return True
        except requests.RequestException as e:
            logger.warning("Registry publish failed: %s", e)
            return False

    def deprecate(self, skill_id: str, reason: str = "") -> bool:
        """弃用技能"""
        if not skill_id or not isinstance(skill_id, str):
            raise ValueError("skill_id must be a non-empty string")

        payload = {
            "jsonrpc": "2.0",
            "method": "skill.deprecate",
            "params": {"id": skill_id, "reason": reason},
            "id": 3,
        }

        try:
            resp = self._request_with_retry(
                "POST",
                f"{self.config.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            logger.info("Skill deprecated: %s", skill_id)
            return True
        except requests.RequestException as e:
            logger.warning("Registry deprecate failed: %s", e)
            return False

    def get_call_stats(self, skill_id: str) -> dict[str, Any]:
        """获取技能调用统计"""
        if not skill_id or not isinstance(skill_id, str):
            raise ValueError("skill_id must be a non-empty string")

        try:
            resp = self._request_with_retry(
                "GET",
                f"{self.config.base_url}/api/v1/skills/{skill_id}/stats",
                headers=self._auth_headers(),
                timeout=self.config.timeout,
            )
            if resp.status_code == 200:
                data: dict[str, Any] = resp.json()
                return data
        except requests.RequestException as e:
            logger.warning("Failed to get stats for %s: %s", skill_id, e)

        return {"total_calls": 0, "total_revenue": 0.0}

    def invalidate_cache(self, skill_id: str | None = None) -> None:
        """清除缓存"""
        if skill_id:
            keys_to_remove = [k for k in self._cache if k.startswith(skill_id)]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @staticmethod
    def _parse_manifest(data: dict[str, Any]) -> SkillManifest:
        return SkillManifest(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "anonymous"),
            description=data.get("description", ""),
            license_type=data.get("license", "AGPL-3.0"),
            status=SkillStatus(data.get("status", "draft")),
            entry_point=data.get("entry_point"),
            dependencies=data.get("dependencies", []),
            price_per_call=float(data.get("price_per_call", 0.0)),
            metadata=data.get("metadata", {}),
            created_at=float(data.get("created_at", time.time())),
        )
