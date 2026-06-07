#!/usr/bin/env python3
"""Settlement Client — 结算中心协议客户端

职责：
  - 调用记录上报
  - 结算状态查询
  - 自动结算（≤5% 自动处理）
  - 结算报告生成
"""

import logging
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
    platform_fee: float
    ecosystem_fee: float
    contributor_pool: float
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
    """结算中心客户端"""

    PLATFORM_FEE_RATIO = 0.05
    ECOSYSTEM_FEE_RATIO = 0.25
    CONTRIBUTOR_POOL_RATIO = 0.70

    def __init__(self, base_url: str = "http://localhost:8080", api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key
        self._pending_records: list[SettlementRecord] = []
        self._settled_records: list[SettlementRecord] = []

    def submit_record(self, record: SettlementRecord) -> bool:
        """上报结算记录"""
        record.platform_fee = record.amount_usd * self.PLATFORM_FEE_RATIO
        record.ecosystem_fee = record.amount_usd * self.ECOSYSTEM_FEE_RATIO
        record.contributor_pool = record.amount_usd * self.CONTRIBUTOR_POOL_RATIO

        self._pending_records.append(record)

        if record.amount_usd <= 0.05:
            return self._auto_settle(record)

        return self._submit_remote(record)

    def get_settlement_status(self, period: str = "daily") -> SettlementReport | None:
        """查询结算状态"""
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/settlements",
                params={"period": period},
                headers=self._auth_headers(),
                timeout=10.0,
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
            resp = requests.post(
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
            resp = requests.post(
                f"{self.base_url}/rpc",
                json=payload,
                headers=self._auth_headers(),
                timeout=10.0,
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
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
