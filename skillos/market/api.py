from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.market.bounties import BountyService
from skillos.market.pricing import PricingEngine
from skillos.market.providers import ProviderProfile, ProviderRegistry
from skillos.market.registry import SkillRegistry
from skillos.market.settlement import SettlementEngine

router = APIRouter(prefix="/market", tags=["market"])


def _get_registry(db: Session = Depends(get_session)) -> SkillRegistry:
    return SkillRegistry(db)


def _get_pricing(db: Session = Depends(get_session)) -> PricingEngine:
    return PricingEngine(db)


def _get_settlement(db: Session = Depends(get_session)) -> SettlementEngine:
    return SettlementEngine(db)


def _get_provider_registry(db: Session = Depends(get_session)) -> ProviderRegistry:
    return ProviderRegistry(db)


def _get_bounty_service(db: Session = Depends(get_session)) -> BountyService:
    return BountyService(db)


@router.post("/register")
def register_skill(
    skill_id: str,
    name: str,
    version: str,
    author: str,
    description: str = "",
    category: str = "general",
    price: float = 0.0,
    registry: SkillRegistry = Depends(_get_registry),
):
    listing = registry.register(
        skill_id=skill_id,
        name=name,
        version=version,
        author=author,
        description=description,
        category=category,
        price_per_call=price,
    )
    return {"success": True, "listing": listing}


@router.get("/search")
def search_skills(
    query: str = Query("", description="Search query"),
    category: str | None = Query(None),
    sort_by: str = Query("popularity", pattern="^(relevance|price_asc|price_desc|rating|popularity)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    registry: SkillRegistry = Depends(_get_registry),
):
    return registry.search(query=query, category=category, sort_by=sort_by, page=page, page_size=page_size)


@router.get("/listings/{listing_id}")
def get_listing(listing_id: str, registry: SkillRegistry = Depends(_get_registry)):
    listing = registry.get_listing(listing_id)
    if not listing:
        return {"error": "Listing not found"}
    return listing


@router.post("/listings/{listing_id}/price")
def price_skill(listing_id: str, pricing: PricingEngine = Depends(_get_pricing)):
    return pricing.calculate_price(listing_id)


@router.post("/listings/{listing_id}/settle")
def settle_skill(
    listing_id: str,
    amount: float,
    period: str = "daily",
    settlement: SettlementEngine = Depends(_get_settlement),
):
    try:
        result = settlement.settle_listing(listing_id, amount, period)
        return {"success": True, "settlement": result}
    except ValueError as e:
        return {"error": str(e)}


@router.get("/settlements/{listing_id}")
def get_settlements(
    listing_id: str,
    period: str | None = Query(None),
    settlement: SettlementEngine = Depends(_get_settlement),
):
    return settlement.get_settlement_history(listing_id=listing_id, period=period)


@router.get("/settlements/{listing_id}/summary")
def settlement_summary(listing_id: str, settlement: SettlementEngine = Depends(_get_settlement)):
    return settlement.get_earnings_summary(listing_id)


@router.post("/listings/{listing_id}/deprecate")
def deprecate_listing(listing_id: str, registry: SkillRegistry = Depends(_get_registry)):
    ok = registry.deprecate(listing_id)
    return {"success": ok}


@router.post("/listings/{listing_id}/reviews")
def add_review(
    listing_id: str,
    reviewer_id: str,
    rating: int = Query(..., ge=1, le=5),
    review_text: str = "",
    registry: SkillRegistry = Depends(_get_registry),
):
    ok = registry.add_review(listing_id, reviewer_id, rating, review_text)
    return {"success": ok}


@router.get("/listings/{listing_id}/reviews")
def get_reviews(listing_id: str, registry: SkillRegistry = Depends(_get_registry)):
    return registry.get_reviews(listing_id)


# ── Provider Profiles ──────────────────────────────────────────────────────


@router.get("/providers/search")
def search_providers(
    query: str = Query(""),
    skill: str | None = Query(None),
    city: str | None = Query(None),
    country: str | None = Query(None),
    max_rate: float | None = Query(None, ge=0),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    registry: ProviderRegistry = Depends(_get_provider_registry),
):
    result = registry.search(
        query=query,
        skill=skill,
        city=city,
        country=country,
        max_rate=max_rate,
        category=category,
        page=page,
        page_size=page_size,
    )
    return {
        "providers": [_serialize_provider(p) for p in result.providers],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }


@router.get("/providers/{provider_id}")
def get_provider(provider_id: str, registry: ProviderRegistry = Depends(_get_provider_registry)):
    profile = registry.get_profile(provider_id)
    if not profile:
        return {"error": "Provider not found"}
    return _serialize_provider(profile)


def _serialize_provider(profile: ProviderProfile) -> dict:
    """公开画像序列化 — 不含电话/收款/私钥等敏感字段。"""
    return {
        "provider_id": profile.provider_id,
        "role": profile.role,
        "headline": profile.headline,
        "bio": profile.bio,
        "skills": profile.skills,
        "categories": profile.categories,
        "city": profile.city,
        "country": profile.country,
        "timezone": profile.timezone,
        "is_remote_available": profile.is_remote_available,
        "hourly_rate": profile.hourly_rate,
        "currency": profile.currency,
        "availability": profile.availability,
        "is_verified": profile.is_verified,
        "profile_complete_score": profile.profile_complete_score,
        "is_profile_complete": profile.is_profile_complete,
        "total_bookings": profile.total_bookings,
        "rating": profile.rating,
        "review_count": profile.review_count,
        "activity_freshness": profile.activity_freshness,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


# ── Bounties ────────────────────────────────────────────────────────────────


@router.post("/bounties")
def create_bounty(
    payload: dict = Body(...),
    service: BountyService = Depends(_get_bounty_service),
):
    dry_run = bool(payload.get("dry_run", False))
    try:
        result = service.create(
            poster_id=payload["poster_id"],            title=payload["title"],
            description=payload.get("description", ""),
            completion_criteria=payload.get("completion_criteria", ""),
            evidence_types=payload.get("evidence_types"),
            price_type=payload.get("price_type", "fixed"),
            price=float(payload.get("price", 0.0)),
            currency=payload.get("currency", "CNY"),
            category=payload.get("category", "general"),
            skill_tags=payload.get("skill_tags"),
            city=payload.get("city", ""),
            country=payload.get("country", ""),
            is_remote_allowed=bool(payload.get("is_remote_allowed", True)),
            deadline=_parse_deadline(payload.get("deadline")),
            spots_available=int(payload.get("spots_available", 1)),
            identity_required=bool(payload.get("identity_required", False)),
            dry_run=dry_run,
        )
    except (ValueError, KeyError, TypeError) as e:
        return {"error": str(e)}
    if dry_run:
        return result
    return {"success": True, "bounty": result}


@router.get("/bounties")
def list_bounties(
    query: str = Query(""),
    category: str | None = Query(None),
    skill: str | None = Query(None),
    city: str | None = Query(None),
    country: str | None = Query(None),
    max_price: float | None = Query(None, ge=0),
    status: str = Query("open"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: BountyService = Depends(_get_bounty_service),
):
    result = service.search(
        query=query,
        category=category,
        skill=skill,
        city=city,
        country=country,
        max_price=max_price,
        status=status,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/bounties/{bounty_id}")
def get_bounty(bounty_id: str, service: BountyService = Depends(_get_bounty_service)):
    bounty = service.get(bounty_id)
    if not bounty:
        return {"error": "Bounty not found"}
    return bounty


@router.post("/bounties/{bounty_id}/publish")
def publish_bounty(bounty_id: str, service: BountyService = Depends(_get_bounty_service)):
    try:
        return {"success": True, "bounty": service.publish(bounty_id)}
    except ValueError as e:
        return {"error": str(e)}


@router.post("/bounties/{bounty_id}/cancel")
def cancel_bounty(bounty_id: str, service: BountyService = Depends(_get_bounty_service)):
    try:
        return {"success": True, "bounty": service.cancel(bounty_id)}
    except ValueError as e:
        return {"error": str(e)}


@router.post("/bounties/{bounty_id}/apply")
def apply_bounty(
    bounty_id: str,
    applicant_id: str = Body(...),
    message: str = Body(""),
    service: BountyService = Depends(_get_bounty_service),
):
    try:
        return {"success": True, "application": service.apply(bounty_id, applicant_id, message)}
    except ValueError as e:
        return {"error": str(e)}


@router.get("/bounties/{bounty_id}/applications")
def list_applications(bounty_id: str, service: BountyService = Depends(_get_bounty_service)):
    return {"applications": service.list_applications(bounty_id)}


@router.post("/bounties/{bounty_id}/applications/{application_id}/accept")
def accept_application(
    bounty_id: str,
    application_id: str,
    service: BountyService = Depends(_get_bounty_service),
):
    try:
        return {"success": True, "bounty": service.accept_application(bounty_id, application_id)}
    except ValueError as e:
        return {"error": str(e)}


@router.post("/bounties/{bounty_id}/submit")
def submit_delivery(
    bounty_id: str,
    evidence: dict = Body(..., embed=True),
    service: BountyService = Depends(_get_bounty_service),
):
    try:
        return {"success": True, "bounty": service.submit_delivery(bounty_id, evidence)}
    except ValueError as e:
        return {"error": str(e)}


@router.post("/bounties/{bounty_id}/confirm")
def confirm_delivery(
    bounty_id: str,
    accepted: bool = Body(True, embed=True),
    service: BountyService = Depends(_get_bounty_service),
):
    try:
        return {"success": True, "bounty": service.confirm_delivery(bounty_id, accepted)}
    except ValueError as e:
        return {"error": str(e)}


@router.post("/bounties/{bounty_id}/settle")
def settle_bounty(bounty_id: str, service: BountyService = Depends(_get_bounty_service)):
    try:
        return {"success": True, "settlement": service.settle(bounty_id)}
    except ValueError as e:
        return {"error": str(e)}


@router.get("/bounties/{bounty_id}/settlements")
def bounty_settlements(
    bounty_id: str,
    db: Session = Depends(get_session),
):
    """查询 bounty 结算记录（5/25/70 记账，走 distribution_records）。"""
    from skillos.db.models import DistributionRecordModel

    rows = (
        db.query(DistributionRecordModel)
        .filter(DistributionRecordModel.skill_id == bounty_id)
        .order_by(DistributionRecordModel.timestamp.desc())
        .all()
    )
    return {
        "bounty_id": bounty_id,
        "settlements": [
            {
                "total_amount": r.total_amount,
                "platform_fee": r.platform_fee,
                "ecosystem_fee": r.ecosystem_fee,
                "contributor_pool": r.contributor_pool,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in rows
        ],
    }


def _parse_deadline(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
