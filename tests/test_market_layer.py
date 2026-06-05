"""Tests for skillos.market — Market Layer (L3)

覆盖:
  - SkillRegistry: 注册、审核、发现、评价
  - PricingEngine: 动态定价
  - SettlementEngine: 结算
"""

import asyncio
import pytest

pytest.importorskip("skillos.market")

from skillos.market.registry import (
    MarketStatus,
    SkillFilters,
    SkillInfo,
    SkillRegistry,
    SkillReview,
    SkillSort,
    SkillVersion,
)
from skillos.market.pricing import PricePoint, PricingEngine
from skillos.market.settlement import (
    SettlementEngine,
    SettlementRecord,
    SettlementResult,
    SettlementStatus,
    TokenType,
)
from skillos._types import SkillManifest


# ---------------------------------------------------------------------------
# SkillRegistry tests
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    @pytest.fixture
    def registry(self, db_session):
        return SkillRegistry(db_session=db_session)

    @pytest.fixture
    def manifest(self):
        return SkillManifest(
            id="skill-market-001",
            name="Test Market Skill",
            version="1.0.0",
            author="tester",
            description="A skill for market testing",
            price_per_call=1.0,
            metadata={"category": "test", "tags": ["demo"]},
        )

    @pytest.mark.asyncio
    async def test_register_skill(self, registry, manifest):
        skill_id = await registry.register_skill(manifest)
        assert skill_id == manifest.id

    @pytest.mark.asyncio
    async def test_approve_skill(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.approve_skill(manifest.id, "admin-001")
        skills = await registry.discover_skills(filters=SkillFilters(status=MarketStatus.APPROVED))
        assert any(s.skill_id == manifest.id for s in skills)

    @pytest.mark.asyncio
    async def test_reject_skill(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.reject_skill(manifest.id, "incomplete docs")
        skills = await registry.discover_skills(filters=SkillFilters(status=MarketStatus.REJECTED))
        assert any(s.skill_id == manifest.id for s in skills)

    @pytest.mark.asyncio
    async def test_deprecate_skill(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.approve_skill(manifest.id, "admin-001")
        await registry.deprecate_skill(manifest.id, "outdated")
        skills = await registry.discover_skills(filters=SkillFilters(status=MarketStatus.DEPRECATED))
        assert any(s.skill_id == manifest.id for s in skills)

    @pytest.mark.asyncio
    async def test_discover_skills_by_query(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.approve_skill(manifest.id, "admin-001")
        skills = await registry.discover_skills(query="Market")
        assert any(s.skill_id == manifest.id for s in skills)

    @pytest.mark.asyncio
    async def test_discover_skills_by_category(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.approve_skill(manifest.id, "admin-001")
        skills = await registry.discover_skills(filters=SkillFilters(category="test"))
        assert any(s.skill_id == manifest.id for s in skills)

    @pytest.mark.asyncio
    async def test_discover_skills_sort_by_rating(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.approve_skill(manifest.id, "admin-001")
        await registry.add_review(manifest.id, "user-001", 5, "great")
        skills = await registry.discover_skills(sort=SkillSort.RATING)
        assert skills[0].skill_id == manifest.id

    @pytest.mark.asyncio
    async def test_get_skill_versions(self, registry, manifest):
        await registry.register_skill(manifest)
        versions = await registry.get_skill_versions(manifest.id)
        assert len(versions) == 1
        assert versions[0].version == "1.0.0"

    @pytest.mark.asyncio
    async def test_add_review(self, registry, manifest):
        await registry.register_skill(manifest)
        review_id = await registry.add_review(manifest.id, "user-001", 4, "good")
        assert review_id
        reviews = await registry.get_reviews(manifest.id)
        assert any(r.review_id == review_id for r in reviews)

    @pytest.mark.asyncio
    async def test_add_review_invalid_rating(self, registry, manifest):
        await registry.register_skill(manifest)
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            await registry.add_review(manifest.id, "user-001", 6)

    @pytest.mark.asyncio
    async def test_increment_call_stats(self, registry, manifest):
        await registry.register_skill(manifest)
        await registry.increment_call_stats(manifest.id, 10.0)
        skills = await registry.discover_skills()
        skill = next((s for s in skills if s.skill_id == manifest.id), None)
        assert skill is not None
        assert skill.total_calls == 1


# ---------------------------------------------------------------------------
# PricingEngine tests
# ---------------------------------------------------------------------------

class TestPricingEngine:
    @pytest.fixture
    def engine(self):
        return PricingEngine()

    def test_set_base_price(self, engine):
        engine.set_base_price("skill-001", 10.0)
        assert engine.get_current_price("skill-001") == 10.0

    def test_calculate_price_default(self, engine):
        engine.set_base_price("skill-001", 10.0)
        price = engine.calculate_price("skill-001")
        assert price == pytest.approx(10.0, abs=1e-6)

    def test_calculate_price_with_demand(self, engine):
        engine.set_base_price("skill-001", 10.0)
        price = engine.calculate_price("skill-001", demand_factor=0.5)
        assert price > 10.0

    def test_calculate_price_with_supply(self, engine):
        engine.set_base_price("skill-001", 10.0)
        engine.record_supply("skill-001", 0.5)
        price = engine.calculate_price("skill-001")
        assert price < 10.0

    def test_calculate_price_bounds(self, engine):
        engine.set_base_price("skill-001", 10.0)
        price = engine.calculate_price("skill-001", demand_factor=10.0)
        assert price <= 50.0  # max 5x base

    def test_calculate_price_zero_base(self, engine):
        price = engine.calculate_price("skill-001")
        assert price == 0.0

    def test_price_history(self, engine):
        engine.set_base_price("skill-001", 10.0)
        engine.calculate_price("skill-001")
        history = engine.get_price_history("skill-001")
        assert len(history) == 1
        assert isinstance(history[0], PricePoint)

    def test_reset_skill(self, engine):
        engine.set_base_price("skill-001", 10.0)
        engine.calculate_price("skill-001")
        engine.reset_skill("skill-001")
        assert engine.get_current_price("skill-001") is None


# ---------------------------------------------------------------------------
# SettlementEngine tests
# ---------------------------------------------------------------------------

class TestSettlementEngine:
    @pytest.fixture
    def engine(self, db_session):
        return SettlementEngine(db_session=db_session)

    @pytest.mark.asyncio
    async def test_settle(self, engine):
        result = await engine.settle(
            call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount=100.0,
            token_type=TokenType.SKILL_COIN,
        )
        assert isinstance(result, SettlementResult)
        assert result.status == SettlementStatus.COMPLETED
        assert result.platform_fee == pytest.approx(5.0, abs=1e-6)
        assert result.ecosystem_fee == pytest.approx(25.0, abs=1e-6)
        assert result.contributor_pool == pytest.approx(70.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_settle_invalid_amount(self, engine):
        with pytest.raises(ValueError, match="Settlement amount must be positive"):
            await engine.settle(
                call_id="call-001",
                skill_id="skill-001",
                caller_id="caller-001",
                amount=0.0,
            )

    @pytest.mark.asyncio
    async def test_get_settlement_history(self, engine):
        await engine.settle(
            call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount=100.0,
        )
        history = await engine.get_settlement_history(skill_id="skill-001")
        assert len(history) == 1
        assert isinstance(history[0], SettlementRecord)

    @pytest.mark.asyncio
    async def test_get_settlement_history_by_caller(self, engine):
        await engine.settle(
            call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount=100.0,
        )
        history = await engine.get_settlement_history(caller_id="caller-001")
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_reverse_settlement(self, engine):
        result = await engine.settle(
            call_id="call-001",
            skill_id="skill-001",
            caller_id="caller-001",
            amount=100.0,
        )
        reversed_result = await engine.reverse_settlement(result.settlement_id, "refund")
        assert reversed_result.status == SettlementStatus.REVERSED

    @pytest.mark.asyncio
    async def test_reverse_settlement_not_found(self, engine):
        with pytest.raises(ValueError, match="Settlement not found"):
            await engine.reverse_settlement("non-existent", "refund")
