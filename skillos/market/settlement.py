import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from skillos.db.models import SettlementModel, SkillListingModel
from skillos.distribution.engine import DistributionEngine


class SettlementPeriod:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


PLATFORM_FEE_RATE = 0.05
ECOSYSTEM_FEE_RATE = 0.25
CONTRIBUTOR_PAYOUT_RATE = 0.70


@dataclass
class SettlementResult:
    id: str
    listing_id: str
    period: str
    total_amount: float
    platform_fee: float
    ecosystem_fee: float
    contributor_payout: float
    status: str
    settled_at: datetime | None
    created_at: datetime


class SettlementEngine:
    def __init__(self, db_session: Session):
        self._db = db_session
        self._dist_engine = DistributionEngine(db_session=db_session)

    def settle_listing(
        self,
        listing_id: str,
        amount: float,
        period: str = SettlementPeriod.DAILY,
        contributor_id: str = "marketplace",
    ) -> SettlementResult:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if not model:
            raise ValueError(f"Listing {listing_id} not found")

        platform_fee = round(amount * PLATFORM_FEE_RATE, 6)
        ecosystem_fee = round(amount * ECOSYSTEM_FEE_RATE, 6)
        contributor_payout = round(amount * CONTRIBUTOR_PAYOUT_RATE, 6)

        now = datetime.now(timezone.utc)
        settlement = SettlementModel(
            id=f"stl-{uuid.uuid4().hex[:12]}",
            listing_id=listing_id,
            period=period,
            total_amount=amount,
            platform_fee=platform_fee,
            ecosystem_fee=ecosystem_fee,
            contributor_payout=contributor_payout,
            status="settled",
            settled_at=now,
        )
        self._db.add(settlement)

        model.total_revenue = round((model.total_revenue or 0.0) + amount, 2)
        self._db.flush()

        return SettlementResult(
            id=settlement.id,
            listing_id=listing_id,
            period=period,
            total_amount=amount,
            platform_fee=platform_fee,
            ecosystem_fee=ecosystem_fee,
            contributor_payout=contributor_payout,
            status="settled",
            settled_at=now,
            created_at=now,
        )

    def settle_period(self, period: str) -> list[SettlementResult]:
        listings = (
            self._db.query(SkillListingModel)
            .filter(SkillListingModel.total_revenue > 0)
            .all()
        )
        results = []
        for listing in listings:
            amount = listing.total_revenue
            if amount <= 0:
                continue
            try:
                result = self.settle_listing(listing.id, amount, period)
                results.append(result)
            except ValueError:
                continue
        return results

    def get_settlement_history(
        self, listing_id: str | None = None, period: str | None = None, limit: int = 50
    ) -> list[SettlementResult]:
        q = self._db.query(SettlementModel)
        if listing_id:
            q = q.filter(SettlementModel.listing_id == listing_id)
        if period:
            q = q.filter(SettlementModel.period == period)
        q = q.order_by(SettlementModel.created_at.desc()).limit(limit)
        return [
            SettlementResult(
                id=r.id,
                listing_id=r.listing_id,
                period=r.period,
                total_amount=r.total_amount,
                platform_fee=r.platform_fee,
                ecosystem_fee=r.ecosystem_fee,
                contributor_payout=r.contributor_payout,
                status=r.status,
                settled_at=r.settled_at,
                created_at=r.created_at,
            )
            for r in q.all()
        ]

    def get_earnings_summary(self, listing_id: str) -> dict:
        from sqlalchemy import func

        stats = (
            self._db.query(
                func.sum(SettlementModel.total_amount),
                func.sum(SettlementModel.platform_fee),
                func.sum(SettlementModel.ecosystem_fee),
                func.sum(SettlementModel.contributor_payout),
                func.count(SettlementModel.id),
            )
            .filter(SettlementModel.listing_id == listing_id)
            .first()
        )

        return {
            "listing_id": listing_id,
            "total_settled": round(stats[0] or 0.0, 6),
            "total_platform_fee": round(stats[1] or 0.0, 6),
            "total_ecosystem_fee": round(stats[2] or 0.0, 6),
            "total_contributor_payout": round(stats[3] or 0.0, 6),
            "settlement_count": stats[4] or 0,
        }
