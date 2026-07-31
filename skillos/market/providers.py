"""Provider Registry — 供应方画像注册中心

职责：
  - 供应方画像的创建、更新、技能/位置/定价/可用性维护
  - 资料完整度计算（is_profile_complete，达标后才进入可搜索列表）
  - 可被 AI 雇佣的供应方搜索（按技能/位置/费率/类别）

画像绑定 Ed25519 身份（provider_id = identities.identity_id）。
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Text, or_
from sqlalchemy.orm import Session

from skillos.db.models import ProviderProfileModel

logger = logging.getLogger(__name__)


VALID_ROLES = ("provider", "consumer", "both")
COMPLETENESS_THRESHOLD = 0.8

COMPLETENESS_WEIGHTS: dict[str, float] = {
    "headline": 0.15,
    "bio": 0.15,
    "skills": 0.25,
    "city": 0.15,
    "hourly_rate": 0.15,
    "availability": 0.15,
}

# 排序权重系数与 DistributionEngine 权重公式保持一致（0.4/0.3/0.2/0.1）
RANK_COEFFICIENTS: dict[str, float] = {
    "bookings": 0.4,
    "rating": 0.3,
    "completeness": 0.2,
    "verification": 0.1,
}

PROFILE_UPDATE_FIELDS = ("headline", "bio", "categories", "gender", "phone")


@dataclass
class ProviderProfile:
    provider_id: str
    role: str
    headline: str
    bio: str
    skills: list[dict[str, Any]]
    categories: list[str]
    city: str
    country: str
    timezone: str
    is_remote_available: bool
    hourly_rate: float
    currency: str
    availability: dict[str, Any]
    is_verified: bool
    profile_complete_score: float
    is_profile_complete: bool
    total_bookings: int
    rating: float
    review_count: int
    activity_freshness: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, model: ProviderProfileModel) -> "ProviderProfile":
        return cls(
            provider_id=model.provider_id,
            role=model.role,
            headline=model.headline,
            bio=model.bio,
            skills=model.skills or [],
            categories=model.categories or [],
            city=model.city,
            country=model.country,
            timezone=model.timezone,
            is_remote_available=model.is_remote_available,
            hourly_rate=model.hourly_rate,
            currency=model.currency,
            availability=model.availability or {},
            is_verified=model.is_verified,
            profile_complete_score=model.profile_complete_score,
            is_profile_complete=model.is_profile_complete,
            total_bookings=model.total_bookings,
            rating=model.rating,
            review_count=model.review_count,
            activity_freshness=model.activity_freshness,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


@dataclass
class ProviderSearchResult:
    providers: list[ProviderProfile]
    total: int
    page: int
    page_size: int


class ProviderRegistry:
    """供应方画像注册中心。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def create_profile(self, provider_id: str, role: str = "provider") -> ProviderProfile:
        """创建供应方画像（角色: provider/consumer/both）。"""
        if not provider_id or not isinstance(provider_id, str):
            raise ValueError("provider_id must be a non-empty string")
        if role not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        if self._db.query(ProviderProfileModel).filter(
            ProviderProfileModel.provider_id == provider_id
        ).first():
            raise ValueError(f"Provider profile already exists: {provider_id}")

        now = datetime.now(timezone.utc)
        model = ProviderProfileModel(
            provider_id=provider_id,
            role=role,
            headline="",
            bio="",
            skills=[],
            categories=[],
            city="",
            country="",
            timezone="",
            is_remote_available=False,
            hourly_rate=0.0,
            currency="CNY",
            availability={},
            is_verified=False,
            profile_complete_score=0.0,
            is_profile_complete=False,
            total_bookings=0,
            rating=0.0,
            review_count=0,
            activity_freshness="new",
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        self._db.flush()
        logger.info("Provider profile created: %s (role=%s)", provider_id, role)
        return ProviderProfile.from_orm(model)

    def get_profile(self, provider_id: str) -> ProviderProfile | None:
        model = self._db.query(ProviderProfileModel).filter(
            ProviderProfileModel.provider_id == provider_id
        ).first()
        return ProviderProfile.from_orm(model) if model else None

    def update_profile(self, provider_id: str, fields: dict[str, Any]) -> ProviderProfile:
        """更新基础画像字段（headline/bio/categories/gender/phone）。"""
        model = self._require(provider_id)
        for key, value in fields.items():
            if key not in PROFILE_UPDATE_FIELDS:
                raise ValueError(f"Field not allowed: {key}")
            setattr(model, key, value)
        self._refresh_completeness(model)
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def add_skill(
        self,
        provider_id: str,
        skill_id: str,
        proficiency: float = 0.5,
        category: str = "general",
    ) -> ProviderProfile:
        """声明技能（引用 Skill 体系，附熟练度）。"""
        model = self._require(provider_id)
        skills = list(model.skills or [])
        if any(s.get("skill_id") == skill_id for s in skills):
            raise ValueError(f"Skill already declared: {skill_id}")
        skills.append(
            {
                "skill_id": skill_id,
                "proficiency": max(0.0, min(1.0, proficiency)),
                "category": category,
            }
        )
        model.skills = skills
        self._refresh_completeness(model)
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def remove_skill(self, provider_id: str, skill_id: str) -> ProviderProfile:
        model = self._require(provider_id)
        model.skills = [s for s in (model.skills or []) if s.get("skill_id") != skill_id]
        self._refresh_completeness(model)
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def set_location(
        self,
        provider_id: str,
        city: str = "",
        country: str = "",
        timezone: str = "",
        is_remote_available: bool = False,
    ) -> ProviderProfile:
        """设置位置画像（决定任务分发半径）。"""
        model = self._require(provider_id)
        model.city = city
        model.country = country
        model.timezone = timezone
        model.is_remote_available = is_remote_available
        self._refresh_completeness(model)
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def set_pricing(self, provider_id: str, hourly_rate: float = 0.0, currency: str = "CNY") -> ProviderProfile:
        """设置按小时费率。"""
        model = self._require(provider_id)
        if hourly_rate < 0:
            raise ValueError("hourly_rate must be >= 0")
        model.hourly_rate = hourly_rate
        model.currency = currency or "CNY"
        self._refresh_completeness(model)
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def set_availability(self, provider_id: str, availability: dict[str, Any]) -> ProviderProfile:
        """设置每周可用时段，如 {"monday": [{"start": "09:00", "end": "17:00"}]}。"""
        model = self._require(provider_id)
        model.availability = availability or {}
        self._refresh_completeness(model)
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def verify(self, provider_id: str) -> ProviderProfile:
        """标记身份已验证（Ed25519 challenge-response 通过后调用）。"""
        model = self._require(provider_id)
        model.is_verified = True
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def compute_completeness(self, provider_id: str) -> dict[str, Any]:
        """计算资料完整度（进度条 + 缺失字段）。"""
        model = self._require(provider_id)
        return self._compute_completeness(model)

    def search(
        self,
        query: str = "",
        skill: str | None = None,
        city: str | None = None,
        country: str | None = None,
        max_rate: float | None = None,
        category: str | None = None,
        only_complete: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> ProviderSearchResult:
        """搜索可雇佣供应方，按画像 rank 降序（完整度默认过滤）。"""
        q = self._db.query(ProviderProfileModel)
        if only_complete:
            q = q.filter(ProviderProfileModel.is_profile_complete.is_(True))
        if query:
            like = f"%{query}%"
            q = q.filter(
                or_(
                    ProviderProfileModel.headline.ilike(like),
                    ProviderProfileModel.bio.ilike(like),
                    ProviderProfileModel.city.ilike(like),
                )
            )
        if city:
            q = q.filter(ProviderProfileModel.city == city)
        if country:
            q = q.filter(ProviderProfileModel.country == country)
        if max_rate is not None:
            q = q.filter(ProviderProfileModel.hourly_rate <= max_rate)
        if category:
            q = q.filter(ProviderProfileModel.categories.any(category))
        if skill:
            q = q.filter(ProviderProfileModel.skills.cast(Text).ilike(f"%{skill}%"))

        total = q.count()
        rows = sorted(q.all(), key=lambda m: self._rank(m), reverse=True)
        start = (page - 1) * page_size
        paged = rows[start : start + page_size]
        return ProviderSearchResult(
            providers=[ProviderProfile.from_orm(m) for m in paged],
            total=total,
            page=page,
            page_size=page_size,
        )

    def record_booking(self, provider_id: str, rating: float | None = None) -> ProviderProfile:
        """记录一次成交；可选附带评分，滚动更新 rating/review_count。"""
        model = self._require(provider_id)
        model.total_bookings = (model.total_bookings or 0) + 1
        if rating is not None:
            rating = max(1, min(5, rating))
            prev = model.rating or 0.0
            count = model.review_count or 0
            model.rating = round((prev * count + rating) / (count + 1), 2)
            model.review_count = count + 1
        self._db.flush()
        return ProviderProfile.from_orm(model)

    def _rank(self, model: ProviderProfileModel) -> float:
        bookings = min(1.0, (model.total_bookings or 0) / 50.0)
        rating = (model.rating or 0.0) / 5.0
        completion = model.profile_complete_score or 0.0
        verified = 1.0 if model.is_verified else 0.0
        return (
            RANK_COEFFICIENTS["bookings"] * bookings
            + RANK_COEFFICIENTS["rating"] * rating
            + RANK_COEFFICIENTS["completeness"] * completion
            + RANK_COEFFICIENTS["verification"] * verified
        )

    def _refresh_completeness(self, model: ProviderProfileModel) -> None:
        info = self._compute_completeness(model)
        model.profile_complete_score = info["score"]
        model.is_profile_complete = info["is_complete"]

    def _compute_completeness(self, model: ProviderProfileModel) -> dict[str, Any]:
        checks = {
            "headline": bool(model.headline),
            "bio": bool(model.bio),
            "skills": bool(model.skills),
            "city": bool(model.city),
            "hourly_rate": (model.hourly_rate or 0.0) > 0,
            "availability": self._has_availability(model.availability),
        }
        missing = [k for k, ok in checks.items() if not ok]
        score = round(sum(COMPLETENESS_WEIGHTS[k] for k in checks if checks[k]), 4)
        return {
            "score": score,
            "is_complete": score >= COMPLETENESS_THRESHOLD,
            "missing_fields": missing,
        }

    @staticmethod
    def _has_availability(availability: dict[str, Any]) -> bool:
        if not availability:
            return False
        return any(bool(slots) for slots in availability.values())

    def _require(self, provider_id: str) -> ProviderProfileModel:
        model = self._db.query(ProviderProfileModel).filter(
            ProviderProfileModel.provider_id == provider_id
        ).first()
        if model is None:
            raise ValueError(f"Provider profile not found: {provider_id}")
        return model
