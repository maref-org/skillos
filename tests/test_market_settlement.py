
from skillos.market.registry import SkillRegistry
from skillos.market.settlement import (
    CONTRIBUTOR_PAYOUT_RATE,
    ECOSYSTEM_FEE_RATE,
    PLATFORM_FEE_RATE,
    SettlementEngine,
    SettlementPeriod,
)


class TestSettlementEngine:
    def _setup_listing(self, db_session):
        reg = SkillRegistry(db_session)
        return reg.register(
            skill_id="sk-stl", name="Settlement Test",
            version="1.0", author="tester",
        )

    def test_settle_listing(self, db_session):
        listing = self._setup_listing(db_session)
        engine = SettlementEngine(db_session)
        result = engine.settle_listing(listing.id, 100.0)
        assert result.listing_id == listing.id
        assert result.total_amount == 100.0
        assert result.status == "settled"
        assert result.settled_at is not None

    def test_settle_correct_fees(self, db_session):
        listing = self._setup_listing(db_session)
        engine = SettlementEngine(db_session)
        result = engine.settle_listing(listing.id, 200.0)
        assert result.platform_fee == round(200.0 * PLATFORM_FEE_RATE, 6)
        assert result.ecosystem_fee == round(200.0 * ECOSYSTEM_FEE_RATE, 6)
        assert result.contributor_payout == round(200.0 * CONTRIBUTOR_PAYOUT_RATE, 6)

    def test_settle_fees_sum_to_total(self, db_session):
        listing = self._setup_listing(db_session)
        engine = SettlementEngine(db_session)
        result = engine.settle_listing(listing.id, 100.0)
        total = result.platform_fee + result.ecosystem_fee + result.contributor_payout
        assert abs(total - 100.0) < 0.001

    def test_settle_updates_listing_revenue(self, db_session):
        listing = self._setup_listing(db_session)
        engine = SettlementEngine(db_session)
        engine.settle_listing(listing.id, 50.0)
        engine.settle_listing(listing.id, 30.0)
        reg = SkillRegistry(db_session)
        updated = reg.get_listing(listing.id)
        assert updated.total_revenue == 80.0

    def test_get_settlement_history(self, db_session):
        listing = self._setup_listing(db_session)
        engine = SettlementEngine(db_session)
        engine.settle_listing(listing.id, 100.0)
        engine.settle_listing(listing.id, 50.0)
        history = engine.get_settlement_history(listing_id=listing.id)
        assert len(history) == 2
        assert history[0].total_amount == 50.0

    def test_get_settlement_history_empty(self, db_session):
        engine = SettlementEngine(db_session)
        history = engine.get_settlement_history(listing_id="nonexistent")
        assert history == []

    def test_get_earnings_summary(self, db_session):
        listing = self._setup_listing(db_session)
        engine = SettlementEngine(db_session)
        engine.settle_listing(listing.id, 100.0)
        summary = engine.get_earnings_summary(listing.id)
        assert summary["total_settled"] == 100.0
        assert summary["settlement_count"] == 1

    def test_settle_nonexistent_listing(self, db_session):
        engine = SettlementEngine(db_session)
        try:
            engine.settle_listing("nope", 100.0)
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_settle_period(self, db_session):
        reg = SkillRegistry(db_session)
        l1 = reg.register(skill_id="sk-p1", name="P1", version="1.0", author="t")
        l2 = reg.register(skill_id="sk-p2", name="P2", version="1.0", author="t")
        reg.record_call(l1.id, revenue=100.0)
        reg.record_call(l2.id, revenue=50.0)

        engine = SettlementEngine(db_session)
        results = engine.settle_period(SettlementPeriod.DAILY)
        assert len(results) >= 2
