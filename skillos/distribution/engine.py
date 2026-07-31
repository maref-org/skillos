#!/usr/bin/env python3
"""Distribution Engine — 5/25/70 经济模型分配引擎

职责：
  - 单笔 Skill 调用收入的 5/25/70 分配
  - 贡献者池内的二级分配（40/20/10/15/15）
  - 动态权重计算
  - 周期结算（日/周/月）

分配流程：
  总收入 $1.00
  ├── 5% → 平台协议维护费
  ├── 25% → OpenClaw 生态基金
  │         ├─ 10% Skill 孵化悬赏
  │         ├─ 5%  基础设施维护
  │         ├─ 5%  负样本收购
  │         ├─ 3%  教育与新用户获取
  │         └─ 2%  风险储备金
  └── 70% → 贡献者池
            按动态权重分配
            ├── 40% → creator
            ├── 20% → worker
            ├── 10% → referrer
            ├── 15% → platform
            └── 15% → community
"""

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from skillos._types import Contributor, SkillCall
from skillos.audit import AuditEventType, log_audit

logger = logging.getLogger(__name__)


class SettlementPeriod(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


ECOSYSTEM_FUND_ALLOCATION = {
    "skill_incubation": 0.10,
    "infrastructure": 0.05,
    "neg_market_acquisition": 0.05,
    "education": 0.03,
    "risk_reserve": 0.02,
}


CONTRIBUTOR_SECONDARY_SPLIT = {
    "creator": 0.40,
    "worker": 0.20,
    "referrer": 0.10,
    "platform": 0.15,
    "community": 0.15,
}


WEIGHT_FORMULA_COEFFICIENTS = {
    "historical_contribution": 0.4,
    "current_attribution": 0.3,
    "success_rate": 0.2,
    "governance_participation": 0.1,
}


@dataclass
class DistributionRecord:
    call_id: str
    skill_id: str
    total_amount: float
    platform_fee: float
    ecosystem_fee: float
    contributor_pool: float
    ecosystem_breakdown: dict[str, float]
    secondary_distribution: dict[str, float]
    timestamp: float = field(default_factory=time.time)


@dataclass
class ContributorPayout:
    contributor_id: str
    amount: float
    weight: float
    roles: dict[str, float]


@dataclass
class SettlementReport:
    period: SettlementPeriod
    period_start: float
    period_end: float
    total_revenue: float
    total_distributions: int
    platform_total: float
    ecosystem_total: float
    contributor_total: float
    payouts: list[ContributorPayout]


class DistributionEngine:
    """5/25/70 分配引擎"""

    PLATFORM_RATIO = 0.05
    ECOSYSTEM_RATIO = 0.25
    CONTRIBUTOR_RATIO = 0.70

    def __init__(self, db_session: Any | None = None) -> None:
        self._distribution_log: list[DistributionRecord] = []
        self._contributor_registry: dict[str, Contributor] = {}
        self._period_revenue: dict[str, float] = {}
        self._db_session = db_session

    def distribute(self, call: SkillCall) -> DistributionRecord:
        """单笔调用的 5/25/70 分配"""
        amount = call.revenue_usd

        platform_fee = amount * self.PLATFORM_RATIO
        ecosystem_fee = amount * self.ECOSYSTEM_RATIO
        contributor_pool = amount * self.CONTRIBUTOR_RATIO

        ecosystem_breakdown = {key: ecosystem_fee * ratio for key, ratio in ECOSYSTEM_FUND_ALLOCATION.items()}

        secondary_distribution = self._compute_secondary_distribution(contributor_pool)

        record = DistributionRecord(
            call_id=call.call_id,
            skill_id=call.skill_id,
            total_amount=amount,
            platform_fee=platform_fee,
            ecosystem_fee=ecosystem_fee,
            contributor_pool=contributor_pool,
            ecosystem_breakdown=ecosystem_breakdown,
            secondary_distribution=secondary_distribution,
        )

        self._distribution_log.append(record)

        if self._db_session is not None:
            from skillos.db.models import DistributionRecordModel

            model = DistributionRecordModel(
                call_id=record.call_id,
                skill_id=record.skill_id,
                total_amount=record.total_amount,
                platform_fee=record.platform_fee,
                ecosystem_fee=record.ecosystem_fee,
                contributor_pool=record.contributor_pool,
                ecosystem_breakdown=record.ecosystem_breakdown,
                secondary_distribution=record.secondary_distribution,
            )
            self._db_session.add(model)
            self._db_session.commit()

        period_key = self._get_current_period_key(SettlementPeriod.DAILY)
        self._period_revenue[period_key] = self._period_revenue.get(period_key, 0.0) + amount

        logger.info(
            "Distributed $%.4f: platform=$%.4f ecosystem=$%.4f contributors=$%.4f",
            amount,
            platform_fee,
            ecosystem_fee,
            contributor_pool,
        )

        log_audit(
            AuditEventType.SETTLEMENT_AUTO,
            call.caller_id,
            call.skill_id,
            "Auto-distribute skill call revenue (5/25/70)",
            {
                "call_id": call.call_id,
                "total_amount": round(amount, 6),
                "platform_fee": round(platform_fee, 6),
                "ecosystem_fee": round(ecosystem_fee, 6),
                "contributor_pool": round(contributor_pool, 6),
            },
        )

        return record

    def calculate_weight(self, contributor: Contributor) -> float:
        """计算贡献者动态权重系数

        个人权重系数 =
            0.4 × 历史贡献度
          + 0.3 × 当期调用归因
          + 0.2 × 成功率评分
          + 0.1 × 社区治理参与
        """
        coeffs = WEIGHT_FORMULA_COEFFICIENTS

        weight = (
            coeffs["historical_contribution"] * contributor.historical_contribution
            + coeffs["current_attribution"] * contributor.current_period_attribution
            + coeffs["success_rate"] * contributor.success_rate
            + coeffs["governance_participation"] * contributor.governance_participation
        )

        return round(min(weight, 1.0), 4)

    def compute_payouts(
        self,
        contributors: list[Contributor],
        total_pool: float,
    ) -> list[ContributorPayout]:
        """按权重计算贡献者 payouts"""
        if not contributors:
            return []

        weights = {c.contributor_id: self.calculate_weight(c) for c in contributors}
        total_weight = sum(weights.values())

        if total_weight == 0:
            return []

        payouts = []
        for c in contributors:
            w = weights[c.contributor_id]
            share = (w / total_weight) * total_pool

            roles = {role: share * ratio for role, ratio in CONTRIBUTOR_SECONDARY_SPLIT.items()}

            payouts.append(
                ContributorPayout(
                    contributor_id=c.contributor_id,
                    amount=round(share, 6),
                    weight=w,
                    roles=roles,
                )
            )

        return sorted(payouts, key=lambda p: p.amount, reverse=True)

    def settle(self, period: SettlementPeriod) -> SettlementReport | None:
        """周期结算（日/周/月）"""
        period_key = self._get_current_period_key(period)
        total_revenue = self._period_revenue.get(period_key, 0.0)

        if total_revenue == 0:
            logger.info("No revenue to settle for period %s", period_key)
            return None

        platform_total = total_revenue * self.PLATFORM_RATIO
        ecosystem_total = total_revenue * self.ECOSYSTEM_RATIO
        contributor_total = total_revenue * self.CONTRIBUTOR_RATIO

        payouts = self.compute_payouts(
            list(self._contributor_registry.values()),
            contributor_total,
        )

        now = time.time()
        report = SettlementReport(
            period=period,
            period_start=self._get_period_start(period),
            period_end=now,
            total_revenue=total_revenue,
            total_distributions=len(self._distribution_log),
            platform_total=platform_total,
            ecosystem_total=ecosystem_total,
            contributor_total=contributor_total,
            payouts=payouts,
        )

        logger.info(
            "Settlement %s: revenue=$%.4f distributions=%d",
            period_key,
            total_revenue,
            len(self._distribution_log),
        )

        log_audit(
            AuditEventType.SETTLEMENT_TRIGGERED,
            "system",
            period.value,
            f"Trigger {period.value} settlement",
            {
                "period_key": period_key,
                "total_revenue": round(total_revenue, 6),
                "total_distributions": len(self._distribution_log),
                "contributor_payouts": len(payouts),
            },
        )

        return report

    def allocate_negmarket_revenue(self, sample_id: str, amount: float, contributor_id: str) -> DistributionRecord:
        """将 NegMarket 反模式 Skill 调用收入纳入 5/25/70 分配"""
        from skillos._types import SkillCall

        call = SkillCall(
            skill_id=f"negmarket:{sample_id}",
            caller_id=contributor_id,
            input_data={},
            revenue_usd=amount,
            status="completed",
        )
        record = self.distribute(call)
        ecosystem_fee = amount * self.ECOSYSTEM_RATIO
        ecosystem_negmarket = ecosystem_fee * ECOSYSTEM_FUND_ALLOCATION["neg_market_acquisition"]
        logger.info(
            "NegMarket revenue $%.4f: ecosystem=$%.4f negmarket_share=$%.4f",
            amount,
            ecosystem_fee,
            ecosystem_negmarket,
        )
        return record

    def register_contributor(self, contributor: Contributor) -> None:
        self._contributor_registry[contributor.contributor_id] = contributor
        if self._db_session is not None:
            from skillos.db.models import ContributorModel

            model = self._db_session.get(ContributorModel, contributor.contributor_id)
            if model is None:
                model = ContributorModel(
                    contributor_id=contributor.contributor_id,
                    name=contributor.name,
                    historical_contribution=contributor.historical_contribution,
                    current_period_attribution=contributor.current_period_attribution,
                    success_rate=contributor.success_rate,
                    governance_participation=contributor.governance_participation,
                )
                self._db_session.add(model)
            else:
                model.name = contributor.name
                model.historical_contribution = contributor.historical_contribution
                model.current_period_attribution = contributor.current_period_attribution
                model.success_rate = contributor.success_rate
                model.governance_participation = contributor.governance_participation
            self._db_session.commit()

    def get_contributor(self, contributor_id: str) -> Contributor | None:
        cached = self._contributor_registry.get(contributor_id)
        if cached is not None:
            return cached
        if self._db_session is not None:
            from skillos.db.models import ContributorModel

            model = self._db_session.get(ContributorModel, contributor_id)
            if model is not None:
                contributor = Contributor(
                    contributor_id=model.contributor_id,
                    name=model.name,
                    historical_contribution=model.historical_contribution,
                    current_period_attribution=model.current_period_attribution,
                    success_rate=model.success_rate,
                    governance_participation=model.governance_participation,
                )
                self._contributor_registry[contributor_id] = contributor
                return contributor
        return None

    def get_distribution_log(self) -> list[DistributionRecord]:
        if self._distribution_log:
            return list(self._distribution_log)
        if self._db_session is not None:
            from skillos.db.models import DistributionRecordModel

            models = (
                self._db_session.query(DistributionRecordModel)
                .order_by(DistributionRecordModel.timestamp.desc())
                .all()
            )
            records = []
            for m in models:
                records.append(
                    DistributionRecord(
                        call_id=m.call_id,
                        skill_id=m.skill_id,
                        total_amount=m.total_amount,
                        platform_fee=m.platform_fee,
                        ecosystem_fee=m.ecosystem_fee,
                        contributor_pool=m.contributor_pool,
                        ecosystem_breakdown=m.ecosystem_breakdown,
                        secondary_distribution=m.secondary_distribution,
                        timestamp=m.timestamp.timestamp(),
                    )
                )
            return records
        return list(self._distribution_log)

    def get_period_revenue(self, period: SettlementPeriod) -> float:
        period_key = self._get_current_period_key(period)
        return self._period_revenue.get(period_key, 0.0)

    @staticmethod
    def _compute_secondary_distribution(contributor_pool: float) -> dict[str, float]:
        return {role: round(contributor_pool * ratio, 6) for role, ratio in CONTRIBUTOR_SECONDARY_SPLIT.items()}

    @staticmethod
    def _get_current_period_key(period: SettlementPeriod) -> str:
        import datetime

        now = datetime.datetime.now(datetime.UTC)
        if period == SettlementPeriod.DAILY:
            return now.strftime("%Y-%m-%d")
        if period == SettlementPeriod.WEEKLY:
            iso = now.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        return now.strftime("%Y-%m")

    @staticmethod
    def _get_period_start(period: SettlementPeriod) -> float:
        import datetime

        now = datetime.datetime.now(datetime.UTC)
        if period == SettlementPeriod.DAILY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == SettlementPeriod.WEEKLY:
            start = now - datetime.timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp()
