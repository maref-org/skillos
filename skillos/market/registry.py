import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.models import SkillListingModel, SkillReviewModel


class ListingStatus:
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUSPENDED = "suspended"


@dataclass
class SkillListing:
    id: str
    skill_id: str
    name: str
    version: str
    author: str
    description: str
    category: str
    tags: list[str]
    price_per_call: float
    status: str
    quality_score: float
    total_calls: int
    total_revenue: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, model: SkillListingModel) -> "SkillListing":
        return cls(
            id=model.id,
            skill_id=model.skill_id,
            name=model.name,
            version=model.version,
            author=model.author,
            description=model.description,
            category=model.category,
            tags=model.tags,
            price_per_call=model.price_per_call,
            status=model.status,
            quality_score=model.quality_score,
            total_calls=model.total_calls,
            total_revenue=model.total_revenue,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


@dataclass
class MarketSearchResult:
    listings: list[SkillListing]
    total: int
    page: int
    page_size: int


class SkillRegistry:
    def __init__(self, db_session: Session):
        self._db = db_session

    def register(
        self,
        skill_id: str,
        name: str,
        version: str,
        author: str,
        description: str = "",
        category: str = "general",
        tags: list[str] | None = None,
        price_per_call: float = 0.0,
    ) -> SkillListing:
        model = SkillListingModel(
            id=f"lst-{uuid.uuid4().hex[:12]}",
            skill_id=skill_id,
            name=name,
            version=version,
            author=author,
            description=description,
            category=category,
            tags=tags or [],
            price_per_call=price_per_call,
            status=ListingStatus.ACTIVE,
            quality_score=0.5,
            total_calls=0,
            total_revenue=0.0,
        )
        self._db.add(model)
        self._db.flush()
        return SkillListing.from_orm(model)

    def search(
        self,
        query: str = "",
        category: str | None = None,
        tags: list[str] | None = None,
        min_quality: float = 0.0,
        max_price: float | None = None,
        sort_by: str = "relevance",
        page: int = 1,
        page_size: int = 20,
    ) -> MarketSearchResult:
        from sqlalchemy import or_

        q = self._db.query(SkillListingModel).filter(SkillListingModel.status == ListingStatus.ACTIVE)

        if query:
            like = f"%{query}%"
            q = q.filter(
                or_(
                    SkillListingModel.name.ilike(like),
                    SkillListingModel.description.ilike(like),
                    SkillListingModel.author.ilike(like),
                )
            )
        if category:
            q = q.filter(SkillListingModel.category == category)
        if tags:
            for tag in tags:
                q = q.filter(SkillListingModel.tags.any(tag))
        if min_quality > 0:
            q = q.filter(SkillListingModel.quality_score >= min_quality)
        if max_price is not None:
            q = q.filter(SkillListingModel.price_per_call <= max_price)

        total = q.count()

        if sort_by == "price_asc":
            q = q.order_by(SkillListingModel.price_per_call.asc())
        elif sort_by == "price_desc":
            q = q.order_by(SkillListingModel.price_per_call.desc())
        elif sort_by == "rating":
            q = q.order_by(SkillListingModel.quality_score.desc())
        elif sort_by == "popularity":
            q = q.order_by(SkillListingModel.total_calls.desc())
        else:
            q = q.order_by(SkillListingModel.total_calls.desc())

        offset = (page - 1) * page_size
        rows = q.offset(offset).limit(page_size).all()

        return MarketSearchResult(
            listings=[SkillListing.from_orm(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_listing(self, listing_id: str) -> SkillListing | None:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        return SkillListing.from_orm(model) if model else None

    def get_listing_by_skill(self, skill_id: str) -> SkillListing | None:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.skill_id == skill_id).first()
        return SkillListing.from_orm(model) if model else None

    def deprecate(self, listing_id: str) -> bool:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if not model:
            return False
        model.status = ListingStatus.DEPRECATED
        self._db.flush()
        return True

    def update_price(self, listing_id: str, new_price: float) -> SkillListing | None:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if not model:
            return None
        model.price_per_call = new_price
        self._db.flush()
        return SkillListing.from_orm(model)

    def update_quality_score(self, listing_id: str, score: float) -> None:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if model:
            model.quality_score = max(0.0, min(1.0, score))
            self._db.flush()

    def record_call(self, listing_id: str, revenue: float = 0.0) -> None:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if model:
            model.total_calls = (model.total_calls or 0) + 1
            model.total_revenue = (model.total_revenue or 0.0) + revenue
            self._db.flush()

    def add_review(self, listing_id: str, reviewer_id: str, rating: int, review_text: str = "") -> bool:
        model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
        if not model:
            return False
        review = SkillReviewModel(
            id=f"rev-{uuid.uuid4().hex[:12]}",
            listing_id=listing_id,
            reviewer_id=reviewer_id,
            rating=max(1, min(5, rating)),
            review_text=review_text,
        )
        self._db.add(review)
        self._db.flush()
        self._recalc_quality(listing_id)
        return True

    def _recalc_quality(self, listing_id: str) -> None:
        from sqlalchemy import func

        stats = (
            self._db.query(func.avg(SkillReviewModel.rating), func.count(SkillReviewModel.id))
            .filter(SkillReviewModel.listing_id == listing_id)
            .first()
        )
        if stats and stats[1] > 0:
            avg_rating = stats[0] / 5.0
            model = self._db.query(SkillListingModel).filter(SkillListingModel.id == listing_id).first()
            if model:
                model.quality_score = round(avg_rating, 4)
                self._db.flush()

    def list_categories(self) -> list[str]:
        rows = (
            self._db.query(SkillListingModel.category)
            .filter(SkillListingModel.status == ListingStatus.ACTIVE)
            .distinct()
            .all()
        )
        return sorted([r[0] for r in rows if r[0]])

    def get_reviews(self, listing_id: str) -> list[dict[str, Any]]:
        rows = (
            self._db.query(SkillReviewModel)
            .filter(SkillReviewModel.listing_id == listing_id)
            .order_by(SkillReviewModel.created_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "reviewer_id": r.reviewer_id,
                "rating": r.rating,
                "review_text": r.review_text,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
