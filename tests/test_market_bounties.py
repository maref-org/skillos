import pytest

from skillos.market.bounties import ApplicationStatus, BountyService, BountyStatus


def _make_bounty(db, poster_id="poster-1", **overrides):
    service = BountyService(db)
    fields = {
        "poster_id": poster_id,
        "title": "Photograph a local cafe",
        "description": "Take 10 photos of the interior and exterior of the cafe.",
        "completion_criteria": "Deliver 10 original photos with clear lighting.",
        "evidence_types": ["photo"],
        "price_type": "fixed",
        "price": 50.0,
        "category": "creative-gigs",
        "city": "Hangzhou",
        "country": "CN",
    }
    fields.update(overrides)
    bounty = service.create(**fields)
    assert not isinstance(bounty, dict)
    return service, bounty


def _open_bounty(db, **overrides):
    service, bounty = _make_bounty(db, **overrides)
    service.publish(bounty.id)
    return service, bounty


def _accepted_bounty(db, applicant="prov-1"):
    service, bounty = _open_bounty(db)
    app = service.apply(bounty.id, applicant, message="I can do this")
    service.accept_application(bounty.id, app.id)
    return service, bounty, app


class TestBountyService:
    def test_create_draft(self, db_session):
        service, bounty = _make_bounty(db_session)
        assert bounty.status == BountyStatus.DRAFT
        assert bounty.price == 50.0
        assert bounty.evidence_types == ["photo"]

    def test_create_dry_run_preview_only(self, db_session):
        service = BountyService(db_session)
        result = service.create(
            poster_id="poster-1",
            title="Dry run task",
            description="A short dry run description",
            completion_criteria="Done.",
            evidence_types=["text"],
            price=10.0,
            dry_run=True,
        )
        assert isinstance(result, dict)
        assert result["dry_run"] is True
        assert result["valid"] is True
        assert BountyService(db_session).search(status=BountyStatus.DRAFT).total == 0

    def test_create_validation_errors(self, db_session):
        service = BountyService(db_session)

        def invalid(**overrides):
            fields = {
                "poster_id": "p",
                "title": "A valid title",
                "description": "enough description here",
                "completion_criteria": "x",
                "evidence_types": ["text"],
                "price": 10.0,
            }
            fields.update(overrides)
            return service.create(**fields)

        with pytest.raises(ValueError, match="title"):
            invalid(title="ok")
        with pytest.raises(ValueError, match="description"):
            invalid(description="short")
        with pytest.raises(ValueError, match="completion_criteria"):
            invalid(completion_criteria="")
        with pytest.raises(ValueError, match="evidence_types"):
            invalid(evidence_types=[])
        with pytest.raises(ValueError, match="invalid evidence"):
            invalid(evidence_types=["audio"])
        with pytest.raises(ValueError, match="price"):
            invalid(price=1.0)

    def test_publish(self, db_session):
        service, bounty = _make_bounty(db_session)
        published = service.publish(bounty.id)
        assert published.status == BountyStatus.OPEN

    def test_publish_incomplete_raises(self, db_session):
        from skillos.db.models import BountyModel

        service, bounty = _make_bounty(db_session)
        db_session.query(BountyModel).filter_by(id=bounty.id).update({"completion_criteria": ""})
        db_session.flush()
        with pytest.raises(ValueError, match="incomplete"):
            service.publish(bounty.id)

    def test_publish_non_draft_raises(self, db_session):
        service, bounty = _open_bounty(db_session)
        with pytest.raises(ValueError, match="draft"):
            service.publish(bounty.id)

    def test_search_open(self, db_session):
        _open_bounty(db_session, title="Photograph a local cafe")
        _open_bounty(db_session, title="Deliver a parcel",
                     description="Pick up and deliver a package across town.")
        service = BountyService(db_session)
        result = service.search(query="cafe")
        assert result.total == 1
        assert "cafe" in result.bounties[0].title
        assert service.search(query="parcel").total == 1

    def test_search_by_city_and_category(self, db_session):
        _open_bounty(db_session)
        _open_bounty(db_session, title="Another task title", city="Beijing")
        service = BountyService(db_session)
        assert service.search(city="Hangzhou").total == 1
        assert service.search(category="creative-gigs").total == 2

    def test_apply(self, db_session):
        service, bounty = _open_bounty(db_session)
        app = service.apply(bounty.id, "prov-1", message="Ready")
        assert app.status == ApplicationStatus.PENDING
        assert app.applicant_id == "prov-1"

    def test_apply_duplicate_raises(self, db_session):
        service, bounty = _open_bounty(db_session)
        service.apply(bounty.id, "prov-1")
        with pytest.raises(ValueError, match="already applied"):
            service.apply(bounty.id, "prov-1")

    def test_apply_closed_bounty_raises(self, db_session):
        service, bounty = _make_bounty(db_session)
        with pytest.raises(ValueError, match="not open"):
            service.apply(bounty.id, "prov-1")

    def test_apply_full_raises(self, db_session):
        service, bounty = _open_bounty(db_session, spots_available=1)
        service.apply(bounty.id, "prov-1")
        service.accept_application(bounty.id, service.list_applications(bounty.id)[0].id)
        with pytest.raises(ValueError, match="not open"):
            service.apply(bounty.id, "prov-2")

    def test_accept_application(self, db_session):
        service, bounty = _open_bounty(db_session)
        app1 = service.apply(bounty.id, "prov-1")
        app2 = service.apply(bounty.id, "prov-2")
        result = service.accept_application(bounty.id, app1.id)
        assert result.status == BountyStatus.ASSIGNED
        assert result.spots_filled == 1
        apps = service.list_applications(bounty.id)
        by_id = {a.id: a.status for a in apps}
        assert by_id[app1.id] == ApplicationStatus.ACCEPTED
        assert by_id[app2.id] == ApplicationStatus.REJECTED

    def test_accept_when_already_assigned_raises(self, db_session):
        service, bounty, app = _accepted_bounty(db_session)
        with pytest.raises(ValueError, match="not open"):
            service.accept_application(bounty.id, app.id)

    def test_submit_delivery_requires_evidence(self, db_session):
        service, bounty, _ = _accepted_bounty(db_session)
        with pytest.raises(ValueError, match="evidence"):
            service.submit_delivery(bounty.id, {})
        submitted = service.submit_delivery(bounty.id, {"photos": ["url1", "url2"]})
        assert submitted.status == BountyStatus.SUBMITTED

    def test_confirm_delivery_accept(self, db_session):
        service, bounty, _ = _accepted_bounty(db_session)
        service.submit_delivery(bounty.id, {"photos": ["url"]})
        result = service.confirm_delivery(bounty.id, accepted=True)
        assert result.status == BountyStatus.WORK_COMPLETED

    def test_confirm_delivery_dispute(self, db_session):
        service, bounty, _ = _accepted_bounty(db_session)
        service.submit_delivery(bounty.id, {"photos": ["url"]})
        result = service.confirm_delivery(bounty.id, accepted=False)
        assert result.status == BountyStatus.DISPUTED

    def test_settle_full_lifecycle(self, db_session):
        service, bounty, _ = _accepted_bounty(db_session)
        service.submit_delivery(bounty.id, {"photos": ["url"]})
        service.confirm_delivery(bounty.id, accepted=True)
        result = service.settle(bounty.id)
        assert result["status"] == BountyStatus.PAID
        assert result["total_amount"] == 50.0
        assert abs(result["platform_fee"] - 2.5) < 1e-6
        assert abs(result["ecosystem_fee"] - 12.5) < 1e-6
        assert abs(result["contributor_pool"] - 35.0) < 1e-6
        assert service.get(bounty.id).status == BountyStatus.PAID

    def test_settle_requires_work_completed(self, db_session):
        service, bounty, _ = _accepted_bounty(db_session)
        with pytest.raises(ValueError, match="work_completed"):
            service.settle(bounty.id)

    def test_cancel_open(self, db_session):
        service, bounty = _open_bounty(db_session)
        assert service.cancel(bounty.id).status == BountyStatus.CANCELLED

    def test_cancel_assigned_raises(self, db_session):
        service, bounty, _ = _accepted_bounty(db_session)
        with pytest.raises(ValueError, match="draft/open"):
            service.cancel(bounty.id)

    def test_list_applications_ordered(self, db_session):
        service, bounty = _open_bounty(db_session)
        service.apply(bounty.id, "prov-1")
        service.apply(bounty.id, "prov-2")
        apps = service.list_applications(bounty.id)
        assert len(apps) == 2
        assert {a.applicant_id for a in apps} == {"prov-1", "prov-2"}

    def test_missing_bounty_raises(self, db_session):
        service = BountyService(db_session)
        assert service.get("bty-nope") is None
        with pytest.raises(ValueError, match="not found"):
            service.publish("bty-nope")
