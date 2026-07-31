"""Phase C-08: E2E — 注册 → 搜索 → 定价 → 调用 → 结算"""

from skillos.market.pricing import PricingEngine
from skillos.market.registry import SkillRegistry
from skillos.market.settlement import SettlementEngine


class TestMarketE2E:
    def test_listing_to_settlement_e2e(self, db_session):
        reg = SkillRegistry(db_session)
        pricing = PricingEngine(db_session)
        settlement = SettlementEngine(db_session)

        listing = reg.register(
            skill_id="sk-e2e", name="E2E Skill", version="1.0",
            author="e2e", description="E2E test", category="utility",
            tags=["e2e"], price_per_call=0.05,
        )

        result = reg.search(query="E2E")
        assert result.total == 1
        assert result.listings[0].id == listing.id

        price_info = pricing.calculate_price(listing.id)
        assert price_info["adjusted_price"] > 0

        reg.record_call(listing.id, revenue=0.05)
        reg.record_call(listing.id, revenue=0.05)

        updated = reg.get_listing(listing.id)
        assert updated.total_calls == 2
        assert updated.total_revenue == 0.10

        settle_result = settlement.settle_listing(listing.id, amount=0.10, period="daily")
        assert settle_result.status == "settled"
        total_fees = settle_result.platform_fee + settle_result.ecosystem_fee + settle_result.contributor_payout
        assert abs(total_fees - 0.10) < 0.001

        summary = settlement.get_earnings_summary(listing.id)
        assert summary["total_settled"] == 0.10
        assert summary["settlement_count"] == 1

    def test_review_to_quality_e2e(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(
            skill_id="sk-revq", name="Quality Skill", version="1.0",
            author="e2e", category="utility",
        )

        reg.add_review(listing.id, "user1", 5, "Excellent")
        reg.add_review(listing.id, "user2", 4, "Good")
        reg.add_review(listing.id, "user3", 3, "Average")

        updated = reg.get_listing(listing.id)
        assert updated.quality_score == 0.8

        pricing = PricingEngine(db_session)
        price_info = pricing.calculate_price(listing.id)
        assert price_info["quality_factor"] > 1.0

    def test_deprecate_hides_from_search(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(
            skill_id="sk-dep-e2e", name="Dep E2E", version="1.0", author="e2e",
        )

        assert reg.search(query="Dep E2E").total == 1
        reg.deprecate(listing.id)
        assert reg.search(query="Dep E2E").total == 0

    def test_multiple_listings_settle_period(self, db_session):
        reg = SkillRegistry(db_session)
        settlement = SettlementEngine(db_session)

        for i in range(3):
            listing_item = reg.register(
                skill_id=f"sk-multi-{i}", name=f"Multi{i}", version="1.0", author="e2e",
            )
            reg.record_call(listing_item.id, revenue=10.0)

        results = settlement.settle_period("weekly")
        assert len(results) >= 3

    def test_price_update_reflected_in_calculation(self, db_session):
        reg = SkillRegistry(db_session)
        pricing = PricingEngine(db_session)
        listing = reg.register(
            skill_id="sk-prupd", name="Price Upd", version="1.0",
            author="e2e", price_per_call=0.10,
        )

        reg.update_price(listing.id, 0.50)
        price_info = pricing.calculate_price(listing.id)
        assert price_info["base_price"] == 0.50
