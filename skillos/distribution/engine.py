#!/usr/bin/env python3
"""Distribution Engine — 5/25/70 经济模型分配引擎

职责：
  - 单笔 Skill 调用收入的 5/25/70 分配
  - 贡献者池内的二级分配（40/20/10/15/15）
  - 动态权重计算
  - 周期结算（日/周/月）

数据持久化：
  - _distribution_log / _contributor_registry 保留为内存缓存
  - DB 为唯一真相源，所有写操作同步到数据库
  - 读操作优先查缓存，miss 时查 DB 并回填
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from skillos.types import Contributor, SkillCall
from skillos.db.engine import get_sessionmaker
from skillos.db.models import ContributorModel, DistributionRecordModel
from skillos.db.repository import ContributorRepository, DistributionRepository

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
    """5/25/70 分配引擎

    数据持久化：
      - 保留内存缓存加速读取
      - DB 为唯一真相源，所有变更同步持久化
    """

    PLATFORM_RATIO = 0.05
    ECOSYSTEM_RATIO = 0.25
    CONTRIBUTOR_RATIO = 0.70

    def __init__(self, db_session: Any | None = None) -> None:
        self._distribution_log: list[DistributionRecord] = []
        self._contributor_registry: dict[str, Contributor] = {}
        self._period_revenue: dict[str, float] = {}
        self._db_session = db_session

    def _get_db(self):
        if self._db_session is not None:
            return self._db_session
        return get_sessionmaker()()

    @staticmethod
    def _record_to_model(record: DistributionRecord) -> DistributionRecordModel:
        return DistributionRecordModel(
            call_id=record.call_id,
            skill_id=record.skill_id,
            total_amount=record.total_amount,
            platform_fee=record.platform_fee,
            ecosystem_fee=record.ecosystem_fee,
            contributor_pool=record.contributor_pool,
            ecosystem_breakdown=record.ecosystem_breakdown,
            secondary_distribution=record.secondary_distribution,
            timestamp=datetime.fromtimestamp(record.timestamp, tz=timezone.utc),
        )

    @staticmethod
    def _model_to_record(model: DistributionRecordModel) -> DistributionRecord:
        return DistributionRecord(
            call_id=model.call_id,
            skill_id=model.skill_id,
            total_amount=model.total_amount,
            platform_fee=model.platform_fee,
            ecosystem_fee=model.ecosystem_fee,
            contributor_pool=model.contributor_pool,
            ecosystem_breakdown=model.ecosystem_breakdown,
            secondary_distribution=model.secondary_distribution,
            timestamp=model.timestamp.timestamp(),
        )

    @staticmethod
    def _contributor_to_model(contributor: Contributor) -> ContributorModel:
        return ContributorModel(
            contributor_id=contributor.contributor_id,
            name=contributor.name,
            historical_contribution=contributor.historical_contribution,
            current_period_attribution=contributor.current_period_attribution,
            success_rate=contributor.success_rate,
            governance_participation=contributor.governance_participation,
        )

    @staticmethod
    def _model_to_contributor(model: ContributorModel) -> Contributor:
        return Contributor(
            contributor_id=model.contributor_id,
            name=model.name,
            historical_contribution=model.historical_contribution,
            current_period_attribution=model.current_period_attribution,
            success_rate=model.success_rate,
            governance_participation=model.governance_participation,
        )

    def distribute(self, call: SkillCall) -> DistributionRecord:
        """单笔调用的 5/25/70 分配"""
        amount = call.revenue_usd

        platform_fee = amount * self.PLATFORM_RATIO
        ecosystem_fee = amount * self.ECOSYSTEM_RATIO
        contributor_pool = amount * self.CONTRIBUTOR_RATIO

        ecosystem_breakdown = {
            key: ecosystem_fee * ratio
            for key, ratio in ECOSYSTEM_FUND_ALLOCATION.items()
        }

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

        # 持久化到 DB
        db = self._get_db()
        try:
            repo = DistributionRepository(db)
            repo.save(self._record_to_model(record))
        finally:
            if self._db_session is None:
                db.close()

        self._distribution_log.append(record)

        period_key = self._get_current_period_key(SettlementPeriod.DAILY)
        self._period_revenue[period_key] = (
            self._period_revenue.get(period_key, 0.0) + amount
        )

        logger.info(
            "Distributed $%.4f: platform=$%.4f ecosystem=$%.4f contributors=$%.4f",
            amount,
            platform_fee,
            ecosystem_fee,
            contributor_pool,
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

            roles = {
                role: share * ratio
                for role, ratio in CONTRIBUTOR_SECONDARY_SPLIT.items()
            }

            payouts.append(ContributorPayout(
                contributor_id=c.contributor_id,
                amount=round(share, 6),
                weight=w,
                roles=roles,
            ))

        return sorted(payouts, key=lambda p: p.amount, reverse=True)

    def settle(self, period: SettlementPeriod) -> SettlementReport | None:
        """周期结算（日/周/月）"""
        period_key = self._get_current_period_key(period)

        # 优先从 DB 聚合当期收入
        db = self._get_db()
        try:
            repo = DistributionRepository(db)
            total_revenue = repo.get_period_revenue(period_key)
        finally:
            if self._db_session is None:
                db.close()

        # 回退到内存缓存
        if total_revenue == 0:
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

        return report

    def register_contributor(self, contributor: Contributor) -> None:
        """注册贡献者（同步到 DB）"""
        db = self._get_db()
        try:
            repo = ContributorRepository(db)
            repo.save(self._contributor_to_model(contributor))
        finally:
            if self._db_session is None:
                db.close()

        self._contributor_registry[contributor.contributor_id] = contributor

    def get_contributor(self, contributor_id: str) -> Contributor | None:
        """获取贡献者（缓存优先，DB 回填）"""
        if contributor_id in self._contributor_registry:
            return self._contributor_registry[contributor_id]

        db = self._get_db()
        try:
            repo = ContributorRepository(db)
            model = repo.get(contributor_id)
            if model is None:
                return None
            contributor = self._model_to_contributor(model)
            self._contributor_registry[contributor_id] = contributor
            return contributor
        finally:
            if self._db_session is None:
                db.close()

    def get_distribution_log(self) -> list[DistributionRecord]:
        """获取分配记录（优先从 DB 加载并刷新缓存）"""
        db = self._get_db()
        try:
            repo = DistributionRepository(db)
            models = repo.list_all(limit=10000)
            records = [self._model_to_record(m) for m in models]
            self._distribution_log = records
            return records
        finally:
            if self._db_session is None:
                db.close()

    def get_period_revenue(self, period: SettlementPeriod) -> float:
        period_key = self._get_current_period_key(period)
        db = self._get_db()
        try:
            repo = DistributionRepository(db)
            db_revenue = repo.get_period_revenue(period_key)
        finally:
            if self._db_session is None:
                db.close()
        return db_revenue if db_revenue else self._period_revenue.get(period_key, 0.0)

    @staticmethod
    def _compute_secondary_distribution(contributor_pool: float) -> dict[str, float]:
        return {
            role: round(contributor_pool * ratio, 6)
            for role, ratio in CONTRIBUTOR_SECONDARY_SPLIT.items()
        }

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
