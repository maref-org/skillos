
from skillos.market.registry import ListingStatus, SkillRegistry


class TestSkillRegistry:
    def test_register_skill(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(
            skill_id="sk-001", name="Test Skill", version="1.0",
            author="tester", description="A test skill", category="utility",
            tags=["test", "demo"], price_per_call=0.01,
        )
        assert listing.name == "Test Skill"
        assert listing.status == ListingStatus.ACTIVE
        assert listing.quality_score == 0.5
        assert listing.skill_id == "sk-001"

    def test_get_listing(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-002", name="Get Test", version="1.0", author="tester")
        found = reg.get_listing(listing.id)
        assert found is not None
        assert found.id == listing.id

    def test_get_listing_not_found(self, db_session):
        reg = SkillRegistry(db_session)
        assert reg.get_listing("nonexistent") is None

    def test_search_by_query(self, db_session):
        reg = SkillRegistry(db_session)
        reg.register(skill_id="sk-a", name="Alpha", version="1.0", author="a", category="nlp")
        reg.register(skill_id="sk-b", name="Beta", version="1.0", author="b", category="vision")
        result = reg.search(query="Alpha")
        assert result.total == 1
        assert result.listings[0].name == "Alpha"

    def test_search_by_category(self, db_session):
        reg = SkillRegistry(db_session)
        reg.register(skill_id="sk-c", name="Cat1", version="1.0", author="c", category="nlp")
        reg.register(skill_id="sk-d", name="Cat2", version="1.0", author="d", category="vision")
        result = reg.search(category="nlp")
        assert result.total == 1

    def test_search_with_pagination(self, db_session):
        reg = SkillRegistry(db_session)
        for i in range(5):
            reg.register(skill_id=f"sk-p{i}", name=f"Page{i}", version="1.0", author="p")
        result = reg.search(page=1, page_size=2)
        assert result.total == 5
        assert len(result.listings) == 2

    def test_deprecate_listing(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-dep", name="Dep Skill", version="1.0", author="t")
        assert reg.deprecate(listing.id) is True
        deprecated = reg.get_listing(listing.id)
        assert deprecated.status == ListingStatus.DEPRECATED

    def test_deprecate_nonexistent(self, db_session):
        reg = SkillRegistry(db_session)
        assert reg.deprecate("nope") is False

    def test_update_price(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-price", name="Price", version="1.0", author="t", price_per_call=0.05)
        updated = reg.update_price(listing.id, 0.10)
        assert updated.price_per_call == 0.10

    def test_record_call(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-call", name="Call Test", version="1.0", author="t")
        reg.record_call(listing.id, revenue=1.0)
        reg.record_call(listing.id, revenue=2.0)
        updated = reg.get_listing(listing.id)
        assert updated.total_calls == 2
        assert updated.total_revenue == 3.0

    def test_add_review_updates_quality(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-rev", name="Review", version="1.0", author="t")
        reg.add_review(listing.id, "user1", 5, "Great!")
        reg.add_review(listing.id, "user2", 3, "OK")
        updated = reg.get_listing(listing.id)
        assert updated.quality_score == 0.8

    def test_get_reviews(self, db_session):
        reg = SkillRegistry(db_session)
        listing = reg.register(skill_id="sk-revs", name="RevList", version="1.0", author="t")
        reg.add_review(listing.id, "u1", 4, "Good")
        reviews = reg.get_reviews(listing.id)
        assert len(reviews) == 1
        assert reviews[0]["rating"] == 4

    def test_list_categories(self, db_session):
        reg = SkillRegistry(db_session)
        reg.register(skill_id="sk-x", name="X", version="1.0", author="x", category="nlp")
        reg.register(skill_id="sk-y", name="Y", version="1.0", author="y", category="vision")
        cats = reg.list_categories()
        assert "nlp" in cats
        assert "vision" in cats
