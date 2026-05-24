#!/usr/bin/env python3
"""Settlement Client — 结算中心协议客户端

职责：
  - 调用记录上报
  - 结算状态查询
  - 自动结算（≤5% 自动处理）
  - 结算报告生成

安全：强制 HTTPS，指数退避重试，熔断保护
"""

import logging
import os
import time
from dataclasses import dataclass, field

import requests  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@dataclass
class SettlementRecord:
    skill_call_id: str
    skill_id: str
    caller_id: str
    amount_usd: float
    platform_fee: float = 0.0
    ecosystem_fee: float = 0.0
    contributor_pool: float = 0.0
    status: str = "pending"
    timestamp: float = field(default_factory=time.time)


@dataclass
class SettlementReport:
    period_start: float
    period_end: float
    total_revenue: float
    total_platform_fees: float
    total_ecosystem_fees: float
    total_contributor_payouts: float
    record_count: int
    status: str


class SettlementClient:
    """结算中心客户端 — 安全增强版"""

    PLATFORM_FEE_RATIO = 0.05
    ECOSYSTEM_FEE_RATIO = 0.25
    CONTRIBUTOR_POOL_RATIO = 0.70

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
    ):
        raw_url = base_url or os.getenv("SKILLOS_SETTLEMENT_URL", "https://localhost:8080")
        self.base_url = self._enforce_https(raw_url)
        self._api_key = api_key or os.getenv("SKILLOS_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._pending_records: list[SettlementRecord] = []
        self._settled_records: list[SettlementRecord] = []
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

        last_exception: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.request(method, url, **kwargs)
                self._record_success()
                return resp
            except requests.RequestException as exc:
                last_exception = exc
                self._record_failure()
                wait = self.retry_backoff * (2 ** attempt)
                logger.warning(
                    "Request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    self.max_retries,
                    wait,
                    exc,
                )
                time.sleep(wait)

        raise last_exception or requests.RequestException("All retries exhausted")

    def submit_record(self, record: SettlementRecord) -> bool:
        """上报结算记录"""
        if not record.skill_call_id or not isinstance(record.skill_call_id, str):
            raise ValueError("skill_call_id must be a non-empty string")
        if not record.skill_id or not isinstance(record.skill_id, str):
            raise ValueError("skill_id must be a non-empty string")
        if record.amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")

        record.platform_fee = record.amount_usd * self.PLATFORM_FEE_RATIO
        record.ecosystem_fee = record.amount_usd * self.ECOSYSTEM_FEE_RATIO
        record.contributor_pool = record.amount_usd * self.CONTRIBUTOR_POOL_RATIO

        self._pending_records.append(record)

        if record.amount_usd <= 0.05:
            return self._auto_settle(record)

        return self._submit_remote(record)

    def get_settlement_status(self, period: str = "daily") -> SettlementReport | None:
        """查询结算状态"""
        if not period or not isinstance(period, str):
            raise ValueError("period must be a non-empty string")

        try:
            resp = self._request_with_retry(
                "GET",
                f"{self.base_url}/api/v1/settlements",
                params={"period": period},
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json()
                return SettlementReport(
                    period_start=data.get("period_start", 0.0),
                    period_end=data.get("period_end", 0.0),
                    total_revenue=data.get("total_revenue", 0.0),
                    total_platform_fees=data.get("platform_fees", 0.0),
                    total_ecosystem_fees=data.get("ecosystem_fees", 0.0),
                    total_contributor_payouts=data.get("contributor_payouts", 0.0),
                    record_count=data.get("record_count", 0),
                    status=data.get("status", "pending"),
                )
        except requests.RequestException as e:
            logger.warning("Failed to get settlement status: %s", e)

        return None

    def trigger_settlement(self, period_start: float, period_end: float) -> SettlementReport | None:
        """触发周期结算"""
        if period_start >= period_end:
            raise ValueError("period_start must be < period_end")

        payload = {
            "jsonrpc": "2.0",
            "method": "settlement.trigger",
            "params": {
                "period_start": period_start,
                "period_end": period_end,
            },
            "id": 1,
        }

        try:
            resp = self._request_with_retry(
                "POST",
                f"{self.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

            result = data.get("result", {})
            return SettlementReport(
                period_start=period_start,
                period_end=period_end,
                total_revenue=result.get("total_revenue", 0.0),
                total_platform_fees=result.get("platform_fees", 0.0),
                total_ecosystem_fees=result.get("ecosystem_fees", 0.0),
                total_contributor_payouts=result.get("contributor_payouts", 0.0),
                record_count=result.get("record_count", 0),
                status=result.get("status", "completed"),
            )
        except requests.RequestException as e:
            logger.warning("Settlement trigger failed: %s", e)
            return None

    def get_pending_count(self) -> int:
        return len(self._pending_records)

    def compute_split(self, amount_usd: float) -> dict[str, float]:
        """计算 5/25/70 分配"""
        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        return {
            "platform_fee": round(amount_usd * self.PLATFORM_FEE_RATIO, 6),
            "ecosystem_fee": round(amount_usd * self.ECOSYSTEM_FEE_RATIO, 6),
            "contributor_pool": round(amount_usd * self.CONTRIBUTOR_POOL_RATIO, 6),
        }

    def _auto_settle(self, record: SettlementRecord) -> bool:
        record.status = "auto_settled"
        self._pending_records.remove(record)
        self._settled_records.append(record)
        logger.debug("Auto-settled record: %s ($%.4f)", record.skill_call_id, record.amount_usd)
        return True

    def _submit_remote(self, record: SettlementRecord) -> bool:
        payload = {
            "jsonrpc": "2.0",
            "method": "settlement.submit",
            "params": {
                "skill_call_id": record.skill_call_id,
                "skill_id": record.skill_id,
                "caller_id": record.caller_id,
                "amount_usd": record.amount_usd,
                "platform_fee": record.platform_fee,
                "ecosystem_fee": record.ecosystem_fee,
                "contributor_pool": record.contributor_pool,
            },
            "id": 2,
        }

        try:
            resp = self._request_with_retry(
                "POST",
                f"{self.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                record.status = "submitted"
                self._pending_records.remove(record)
                self._settled_records.append(record)
                return True
        except requests.RequestException as e:
            logger.warning("Remote settlement submit failed: %s", e)

        return False

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
