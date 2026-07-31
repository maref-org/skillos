import pytest

from skillos.db.models import IdentityModel
from skillos.market.providers import ProviderRegistry


def _identity(db, identity_id: str):
    db.add(IdentityModel(identity_id=identity_id, public_key_pem="fake-key"))
    db.flush()


def _complete_profile(db, provider_id="prov-1"):
    reg = ProviderRegistry(db)
    if reg.get_profile(provider_id) is None:
        reg.create_profile(provider_id)
    reg.update_profile(provider_id, {"headline": "Freelance photographer", "bio": "I take photos."})
    reg.add_skill(provider_id, "sk-photo", proficiency=0.9, category="photography")
    reg.set_location(provider_id, city="Hangzhou", country="CN", timezone="Asia/Shanghai")
    reg.set_pricing(provider_id, hourly_rate=100.0)
    reg.set_availability(provider_id, {"monday": [{"start": "09:00", "end": "17:00"}]})
    return reg.get_profile(provider_id)


class TestProviderRegistry:
    def test_create_profile(self, db_session):
        _identity(db_session, "p1")
        reg = ProviderRegistry(db_session)
        profile = reg.create_profile("p1", role="both")
        assert profile.provider_id == "p1"
        assert profile.role == "both"
        assert profile.is_profile_complete is False

    def test_create_duplicate_raises(self, db_session):
        _identity(db_session, "p2")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p2")
        with pytest.raises(ValueError, match="already exists"):
            reg.create_profile("p2")

    def test_create_invalid_role(self, db_session):
        reg = ProviderRegistry(db_session)
        with pytest.raises(ValueError, match="role"):
            reg.create_profile("p3", role="hacker")

    def test_get_profile(self, db_session):
        _identity(db_session, "p4")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p4")
        assert reg.get_profile("p4").provider_id == "p4"
        assert reg.get_profile("missing") is None

    def test_update_profile_fields(self, db_session):
        _identity(db_session, "p5")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p5")
        profile = reg.update_profile("p5", {"headline": "Designer", "bio": "UI/UX"})
        assert profile.headline == "Designer"
        assert profile.bio == "UI/UX"

    def test_update_profile_disallows_unknown_field(self, db_session):
        _identity(db_session, "p6")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p6")
        with pytest.raises(ValueError, match="Field not allowed"):
            reg.update_profile("p6", {"hourly_rate": 999})

    def test_add_and_remove_skill(self, db_session):
        _identity(db_session, "p7")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p7")
        reg.add_skill("p7", "sk-a", proficiency=0.8, category="data")
        skills = reg.get_profile("p7").skills
        assert skills == [{"skill_id": "sk-a", "proficiency": 0.8, "category": "data"}]
        reg.remove_skill("p7", "sk-a")
        assert reg.get_profile("p7").skills == []

    def test_add_skill_duplicate_raises(self, db_session):
        _identity(db_session, "p8")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p8")
        reg.add_skill("p8", "sk-a")
        with pytest.raises(ValueError, match="already declared"):
            reg.add_skill("p8", "sk-a")

    def test_verify(self, db_session):
        _identity(db_session, "p9")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p9")
        assert reg.get_profile("p9").is_verified is False
        reg.verify("p9")
        assert reg.get_profile("p9").is_verified is True

    def test_completeness_missing_fields(self, db_session):
        _identity(db_session, "p10")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p10")
        info = reg.compute_completeness("p10")
        assert info["score"] == 0.0
        assert info["is_complete"] is False
        assert sorted(info["missing_fields"]) == [
            "availability",
            "bio",
            "city",
            "headline",
            "hourly_rate",
            "skills",
        ]

    def test_complete_profile_threshold(self, db_session):
        _identity(db_session, "p11")
        profile = _complete_profile(db_session, "p11")
        assert profile.profile_complete_score == 1.0
        assert profile.is_profile_complete is True

    def test_partial_profile_not_complete(self, db_session):
        _identity(db_session, "p12")
        reg = ProviderRegistry(db_session)
        reg.create_profile("p12")
        reg.update_profile("p12", {"headline": "Writer"})
        reg.add_skill("p12", "sk-w", category="writing")
        profile = reg.get_profile("p12")
        assert profile.is_profile_complete is False
        assert 0.4 <= profile.profile_complete_score < 0.8

    def test_search_filters_complete_profiles(self, db_session):
        _identity(db_session, "pa")
        _identity(db_session, "pb")
        reg = ProviderRegistry(db_session)
        reg.create_profile("pa")
        reg.create_profile("pb")
        _complete_profile(db_session, "pa")
        result = reg.search()
        assert result.total == 1
        assert result.providers[0].provider_id == "pa"

    def test_search_by_skill(self, db_session):
        _identity(db_session, "pc")
        reg = ProviderRegistry(db_session)
        _complete_profile(db_session, "pc")
        assert reg.search(skill="photo").total == 1
        assert reg.search(skill="cooking").total == 0

    def test_search_by_city_and_max_rate(self, db_session):
        _identity(db_session, "pd")
        reg = ProviderRegistry(db_session)
        _complete_profile(db_session, "pd")
        assert reg.search(city="Hangzhou").total == 1
        assert reg.search(city="Beijing").total == 0
        assert reg.search(max_rate=200.0).total == 1
        assert reg.search(max_rate=50.0).total == 0

    def test_search_rank_prefers_verified_and_bookings(self, db_session):
        _identity(db_session, "p1")
        _identity(db_session, "p2")
        reg = ProviderRegistry(db_session)
        _complete_profile(db_session, "p1")
        _complete_profile(db_session, "p2")
        reg.verify("p1")
        reg.record_booking("p1", rating=5)
        result = reg.search()
        assert result.providers[0].provider_id == "p1"

    def test_record_booking_updates_rating(self, db_session):
        _identity(db_session, "pe")
        reg = ProviderRegistry(db_session)
        _complete_profile(db_session, "pe")
        reg.record_booking("pe", rating=5)
        reg.record_booking("pe", rating=3)
        profile = reg.get_profile("pe")
        assert profile.total_bookings == 2
        assert profile.rating == 4.0
        assert profile.review_count == 2

    def test_missing_profile_raises(self, db_session):
        reg = ProviderRegistry(db_session)
        assert reg.get_profile("nope") is None
        with pytest.raises(ValueError, match="not found"):
            reg.verify("nope")
