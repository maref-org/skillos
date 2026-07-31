import uuid

from skillos.market.pricing import PricingEngine
from skillos.market.registry import SkillRegistry


class TestPricingEngine:
    def _setup_listing(self, db_session, category="general", price=0.05, calls=0):
        reg = SkillRegistry(db_session)
        listing = reg.register(
            skill_id=f"sk-{uuid.uuid4().hex[:8]}",
            name="Pricing Test",
            version="1.0",
            author="tester",
            category=category,
            price_per_call=price,
        )
        for _ in range(calls):
            reg.record_call(listing.id)
        return listing

    def test_calculate_price_returns_all_factors(self, db_session):
        listing = self._setup_listing(db_session)
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price(listing.id)
        assert "base_price" in result
        assert "supply_factor" in result
        assert "demand_factor" in result
        assert "quality_factor" in result
        assert "adjusted_price" in result

    def test_low_supply_increases_price(self, db_session):
        listing = self._setup_listing(db_session, category="rare_category")
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price(listing.id)
        assert result["supply_factor"] >= 1.0
        assert result["adjusted_price"] > result["base_price"]

    def test_high_demand_increases_price(self, db_session):
        listing = self._setup_listing(db_session, calls=100)
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price(listing.id)
        assert result["demand_factor"] > 1.0

    def test_low_quality_reduces_price(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-lowq", name="LowQ", version="1.0", author="t")
        reg.update_quality_score(listing.id, 0.2)
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price(listing.id)
        assert result["quality_factor"] < 1.0

    def test_high_quality_increases_price(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-highq", name="HighQ", version="1.0", author="t")
        reg.update_quality_score(listing.id, 0.9)
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price(listing.id)
        assert result["quality_factor"] > 1.0

    def test_price_never_below_minimum(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(
            skill_id="sk-min", name="Min", version="1.0", author="t", price_per_call=0.0,
        )
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price(listing.id)
        assert result["adjusted_price"] >= 0.001

    def test_compute_optimal_price(self, db_session):
        listing = self._setup_listing(db_session)
        pricing = PricingEngine(db_session)
        result = pricing.compute_optimal_price(listing.id)
        assert "optimal_price" in result
        assert "competitor_count" in result
        assert result["optimal_price"] > 0

    def test_compute_optimal_with_max_price(self, db_session):
        listing = self._setup_listing(db_session, price=10.0)
        pricing = PricingEngine(db_session)
        result = pricing.compute_optimal_price(listing.id, max_price=1.0)
        assert result["optimal_price"] <= 1.0

    def test_nonexistent_listing_returns_error(self, db_session):
        pricing = PricingEngine(db_session)
        result = pricing.calculate_price("nope")
        assert "error" in result




