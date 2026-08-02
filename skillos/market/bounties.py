"""Bounty Service — 任务发布、申请、验收与结算

状态机: draft → open → assigned → submitted → work_completed → paid
另有 cancelled / disputed（争议冻结）。

定位为协议内核记账层：结算复用 DistributionEngine（5/25/70），
不托管真实资金，法币支付由下游持牌平台承接。
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Text, or_
from sqlalchemy.orm import Session

from skillos.audit import AuditEventType, log_audit
from skillos.db.models import BountyApplicationModel, BountyModel
from skillos.distribution.engine import DistributionEngine
from skillos.types import SkillCall

logger = logging.getLogger(__name__)


class BountyStatus:
    DRAFT = "draft"
    OPEN = "open"
    ASSIGNED = "assigned"
    SUBMITTED = "submitted"
    WORK_COMPLETED = "work_completed"
    PAID = "paid"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class ApplicationStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


VALID_EVIDENCE_TYPES = ("text", "photo", "video", "link")
VALID_PRICE_TYPES = ("fixed", "hourly")
MIN_PRICE = 5.0


@dataclass
class Bounty:
    id: str
    poster_id: str
    title: str
    description: str
    completion_criteria: str
    evidence_types: list[str]
    price_type: str
    price: float
    currency: str
    category: str
    skill_tags: list[str]
    city: str
    country: str
    is_remote_allowed: bool
    deadline: datetime | None
    spots_available: int
    spots_filled: int
    identity_required: bool
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, model: BountyModel) -> "Bounty":
        return cls(
            id=model.id,
            poster_id=model.poster_id,
            title=model.title,
            description=model.description,
            completion_criteria=model.completion_criteria,
            evidence_types=model.evidence_types or [],
            price_type=model.price_type,
            price=model.price,
            currency=model.currency,
            category=model.category,
            skill_tags=model.skill_tags or [],
            city=model.city,
            country=model.country,
            is_remote_allowed=model.is_remote_allowed,
            deadline=model.deadline,
            spots_available=model.spots_available,
            spots_filled=model.spots_filled,
            identity_required=model.identity_required,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


@dataclass
class BountyApplication:
    id: str
    bounty_id: str
    applicant_id: str
    message: str
    status: str
    applied_at: datetime

    @classmethod
    def from_orm(cls, model: BountyApplicationModel) -> "BountyApplication":
        return cls(
            id=model.id,
            bounty_id=model.bounty_id,
            applicant_id=model.applicant_id,
            message=model.message,
            status=model.status,
            applied_at=model.applied_at,
        )


@dataclass
class BountySearchResult:
    bounties: list[Bounty]
    total: int
    page: int
    page_size: int


class BountyService:
    """Bounty 生命周期服务。"""

    def __init__(self, db_session: Session):
        self._db = db_session
        self._dist = DistributionEngine(db_session)

    def create(
        self,
        poster_id: str,
        title: str,
        description: str = "",
        completion_criteria: str = "",
        evidence_types: list[str] | None = None,
        price_type: str = "fixed",
        price: float = 0.0,
        currency: str = "CNY",
        category: str = "general",
        skill_tags: list[str] | None = None,
        city: str = "",
        country: str = "",
        is_remote_allowed: bool = True,
        deadline: datetime | None = None,
        spots_available: int = 1,
        identity_required: bool = False,
        dry_run: bool = False,
    ) -> Bounty | dict[str, Any]:
        """创建 bounty；dry_run=True 仅校验并返回预览，不落库。"""
        if not poster_id or not isinstance(poster_id, str):
            raise ValueError("poster_id must be a non-empty string")
        evidence_types = evidence_types or []
        skill_tags = skill_tags or []

        errors = self._validate(
            title=title,
            description=description,
            completion_criteria=completion_criteria,
            evidence_types=evidence_types,
            price_type=price_type,
            price=price,
            spots_available=spots_available,
        )
        if errors:
            raise ValueError("; ".join(errors))

        if dry_run:
            return {
                "dry_run": True,
                "valid": True,
                "preview": {
                    "poster_id": poster_id,
                    "title": title,
                    "completion_criteria": completion_criteria,
                    "evidence_types": evidence_types,
                    "price_type": price_type,
                    "price": price,
                },
            }

        now = datetime.now(timezone.utc)
        model = BountyModel(
            id=f"bty-{uuid.uuid4().hex[:12]}",
            poster_id=poster_id,
            title=title,
            description=description,
            completion_criteria=completion_criteria,
            evidence_types=evidence_types,
            price_type=price_type,
            price=price,
            currency=currency or "CNY",
            category=category or "general",
            skill_tags=skill_tags,
            city=city,
            country=country,
            is_remote_allowed=is_remote_allowed,
            deadline=deadline,
            spots_available=spots_available,
            spots_filled=0,
            identity_required=identity_required,
            status=BountyStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        self._db.flush()
        log_audit(
            AuditEventType.SKILL_REGISTERED,
            poster_id,
            model.id,
            "Create bounty (draft)",
            {"title": title, "price": price, "price_type": price_type},
        )
        return Bounty.from_orm(model)

    def publish(self, bounty_id: str) -> Bounty:
        """发布 bounty（draft → open），发布前复验必填字段。"""
        model = self._require(bounty_id)
        if model.status != BountyStatus.DRAFT:
            raise ValueError(f"Only draft bounties can be published, current: {model.status}")
        errors = self._validate(
            title=model.title,
            description=model.description,
            completion_criteria=model.completion_criteria,
            evidence_types=model.evidence_types or [],
            price_type=model.price_type,
            price=model.price,
            spots_available=model.spots_available,
        )
        if errors:
            raise ValueError(f"Cannot publish incomplete bounty: {'; '.join(errors)}")
        model.status = BountyStatus.OPEN
        self._db.flush()
        log_audit(
            AuditEventType.SKILL_PUBLISHED,
            model.poster_id,
            bounty_id,
            "Publish bounty",
            {"status": BountyStatus.OPEN},
        )
        return Bounty.from_orm(model)

    def search(
        self,
        query: str = "",
        category: str | None = None,
        skill: str | None = None,
        city: str | None = None,
        country: str | None = None,
        max_price: float | None = None,
        status: str = BountyStatus.OPEN,
        page: int = 1,
        page_size: int = 20,
        poster_id: str | None = None,
    ) -> BountySearchResult:
        q = self._db.query(BountyModel).filter(BountyModel.status == status)
        if poster_id:
            q = q.filter(BountyModel.poster_id == poster_id)
        if query:
            like = f"%{query}%"
            q = q.filter(
                or_(
                    BountyModel.title.ilike(like),
                    BountyModel.description.ilike(like),
                )
            )
        if category:
            q = q.filter(BountyModel.category == category)
        if city:
            q = q.filter(BountyModel.city == city)
        if country:
            q = q.filter(BountyModel.country == country)
        if max_price is not None:
            q = q.filter(BountyModel.price <= max_price)
        if skill:
            q = q.filter(BountyModel.skill_tags.cast(Text).ilike(f"%{skill}%"))

        total = q.count()
        q = q.order_by(BountyModel.created_at.desc())
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
        return BountySearchResult(
            bounties=[Bounty.from_orm(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def get(self, bounty_id: str) -> Bounty | None:
        model = self._db.query(BountyModel).filter(BountyModel.id == bounty_id).first()
        return Bounty.from_orm(model) if model else None

    def apply(self, bounty_id: str, applicant_id: str, message: str = "") -> BountyApplication:
        """申请 bounty（仅 open 状态且未满员）。"""
        model = self._require(bounty_id)
        if model.status != BountyStatus.OPEN:
            raise ValueError(f"Bounty is not open for applications, current: {model.status}")
        if (model.spots_filled or 0) >= (model.spots_available or 1):
            raise ValueError("No spots available for this bounty")
        if self._db.query(BountyApplicationModel).filter(
            BountyApplicationModel.bounty_id == bounty_id,
            BountyApplicationModel.applicant_id == applicant_id,
        ).first():
            raise ValueError(f"Provider already applied to this bounty: {applicant_id}")

        app = BountyApplicationModel(
            id=f"app-{uuid.uuid4().hex[:12]}",
            bounty_id=bounty_id,
            applicant_id=applicant_id,
            message=message,
            status=ApplicationStatus.PENDING,
            applied_at=datetime.now(timezone.utc),
        )
        self._db.add(app)
        self._db.flush()
        return BountyApplication.from_orm(app)

    def accept_application(self, bounty_id: str, application_id: str) -> Bounty:
        """接受申请（bounty → assigned），并自动拒绝其余 pending 申请。"""
        model = self._require(bounty_id)
        if model.status != BountyStatus.OPEN:
            raise ValueError(f"Bounty is not open, current: {model.status}")
        app = self._db.query(BountyApplicationModel).filter(
            BountyApplicationModel.id == application_id,
            BountyApplicationModel.bounty_id == bounty_id,
        ).first()
        if app is None:
            raise ValueError(f"Application not found for bounty: {application_id}")
        if app.status != ApplicationStatus.PENDING:
            raise ValueError("Application already processed")

        app.status = ApplicationStatus.ACCEPTED
        model.status = BountyStatus.ASSIGNED
        model.spots_filled = (model.spots_filled or 0) + 1
        self._db.query(BountyApplicationModel).filter(
            BountyApplicationModel.bounty_id == bounty_id,
            BountyApplicationModel.status == ApplicationStatus.PENDING,
        ).update({BountyApplicationModel.status: ApplicationStatus.REJECTED})
        self._db.flush()
        log_audit(
            AuditEventType.AUTH_SUCCESS,
            model.poster_id,
            bounty_id,
            "Accept bounty application",
            {"application_id": application_id, "applicant_id": app.applicant_id},
        )
        return Bounty.from_orm(model)

    def reject_application(self, bounty_id: str, application_id: str) -> None:
        app = self._db.query(BountyApplicationModel).filter(
            BountyApplicationModel.id == application_id,
            BountyApplicationModel.bounty_id == bounty_id,
        ).first()
        if app is None:
            raise ValueError(f"Application not found for bounty: {application_id}")
        if app.status != ApplicationStatus.PENDING:
            raise ValueError("Application already processed")
        app.status = ApplicationStatus.REJECTED
        self._db.flush()

    def submit_delivery(self, bounty_id: str, evidence: dict[str, Any]) -> Bounty:
        """回传交付证据（assigned → submitted）。证据经审计日志留存。"""
        model = self._require(bounty_id)
        if model.status != BountyStatus.ASSIGNED:
            raise ValueError(f"Bounty is not in progress, current: {model.status}")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("evidence is required")

        model.status = BountyStatus.SUBMITTED
        log_audit(
            AuditEventType.SETTLEMENT_SUBMITTED,
            model.poster_id,
            bounty_id,
            "Submit bounty delivery",
            {"evidence": evidence},
        )
        self._db.flush()
        return Bounty.from_orm(model)

    def confirm_delivery(self, bounty_id: str, accepted: bool = True) -> Bounty:
        """验收确认（submitted → work_completed / disputed）。"""
        model = self._require(bounty_id)
        if model.status != BountyStatus.SUBMITTED:
            raise ValueError(f"Bounty has no delivery to confirm, current: {model.status}")
        model.status = BountyStatus.WORK_COMPLETED if accepted else BountyStatus.DISPUTED
        self._db.flush()
        return Bounty.from_orm(model)

    def settle(self, bounty_id: str) -> dict[str, Any]:
        """结算（work_completed → paid），复用 5/25/70 分配引擎记账。"""
        model = self._require(bounty_id)
        if model.status != BountyStatus.WORK_COMPLETED:
            raise ValueError(f"Only work_completed bounties can be settled, current: {model.status}")

        call = SkillCall(
            skill_id=bounty_id,
            caller_id=model.poster_id,
            input_data={"bounty_id": bounty_id, "kind": "bounty"},
            revenue_usd=model.price,
            status="settled",
        )
        record = self._dist.distribute(call)
        model.status = BountyStatus.PAID
        self._db.flush()
        return {
            "bounty_id": bounty_id,
            "status": BountyStatus.PAID,
            "total_amount": record.total_amount,
            "platform_fee": record.platform_fee,
            "ecosystem_fee": record.ecosystem_fee,
            "contributor_pool": record.contributor_pool,
        }

    def cancel(self, bounty_id: str) -> Bounty:
        """取消 bounty（draft/open → cancelled）。"""
        model = self._require(bounty_id)
        if model.status not in (BountyStatus.DRAFT, BountyStatus.OPEN):
            raise ValueError(f"Only draft/open bounties can be cancelled, current: {model.status}")
        model.status = BountyStatus.CANCELLED
        self._db.flush()
        return Bounty.from_orm(model)

    def list_applications(self, bounty_id: str) -> list[BountyApplication]:
        rows = (
            self._db.query(BountyApplicationModel)
            .filter(BountyApplicationModel.bounty_id == bounty_id)
            .order_by(BountyApplicationModel.applied_at.desc())
            .all()
        )
        return [BountyApplication.from_orm(r) for r in rows]

    def _validate(
        self,
        title: str,
        description: str,
        completion_criteria: str,
        evidence_types: list[str],
        price_type: str,
        price: float,
        spots_available: int,
    ) -> list[str]:
        errors: list[str] = []
        if not title or len(title) < 5 or len(title) > 200:
            errors.append("title must be 5-200 characters")
        if len(description) < 10:
            errors.append("description must be at least 10 characters")
        if not completion_criteria:
            errors.append("completion_criteria is required")
        if not evidence_types:
            errors.append("evidence_types is required")
        else:
            invalid = [e for e in evidence_types if e not in VALID_EVIDENCE_TYPES]
            if invalid:
                errors.append(f"invalid evidence types: {invalid}")
        if price_type not in VALID_PRICE_TYPES:
            errors.append("price_type must be fixed or hourly")
        if (price or 0.0) < MIN_PRICE:
            errors.append(f"price must be >= {MIN_PRICE}")
        if spots_available < 1:
            errors.append("spots_available must be >= 1")
        return errors

    def _require(self, bounty_id: str) -> BountyModel:
        model = self._db.query(BountyModel).filter(BountyModel.id == bounty_id).first()
        if model is None:
            raise ValueError(f"Bounty not found: {bounty_id}")
        return model
