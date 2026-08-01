#!/usr/bin/env python3
"""skillos.db.models — SQLAlchemy 2.0 ORM 数据模型

覆盖核心领域：
- Skill / SkillNFT
- Session
- DistributionRecord / Contributor
- Identity
- AuditLog
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类。"""

    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SkillModel(Base):
    """Skill 持久化模型（替代 _skill_cache）。"""

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    author: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    license_type: Mapped[str] = mapped_column(String(64), default="AGPL-3.0")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    entry_point: Mapped[str | None] = mapped_column(String(256), nullable=True)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    price_per_call: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    nfts: Mapped[list["SkillNFTModel"]] = relationship(back_populates="skill", cascade="all, delete-orphan")


class SkillNFTModel(Base):
    """Skill NFT 持久化模型。"""

    __tablename__ = "skill_nfts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"nft-{uuid.uuid4().hex[:12]}")
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), nullable=False)
    token_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    owner: Mapped[str] = mapped_column(String(256), nullable=False)
    metadata_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    minted_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    skill: Mapped["SkillModel"] = relationship(back_populates="nfts")


class SessionModel(Base):
    """Session 持久化模型（替代 _sessions）。"""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    assets: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DistributionRecordModel(Base):
    """DistributionRecord 持久化模型（替代 _distribution_log）。"""

    __tablename__ = "distribution_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    call_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    platform_fee: Mapped[float] = mapped_column(Float, nullable=False)
    ecosystem_fee: Mapped[float] = mapped_column(Float, nullable=False)
    contributor_pool: Mapped[float] = mapped_column(Float, nullable=False)
    ecosystem_breakdown: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    secondary_distribution: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class ContributorModel(Base):
    """Contributor 持久化模型（替代 _contributor_registry）。"""

    __tablename__ = "contributors"

    contributor_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    historical_contribution: Mapped[float] = mapped_column(Float, default=0.0)
    current_period_attribution: Mapped[float] = mapped_column(Float, default=0.0)
    success_rate: Mapped[float] = mapped_column(Float, default=1.0)
    governance_participation: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class IdentityModel(Base):
    """Identity 持久化模型。"""

    __tablename__ = "identities"

    identity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    public_key_pem: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class AuditLogModel(Base):
    """AuditLog 持久化模型（可选，与文件审计日志并存）。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    prev_hash: Mapped[str] = mapped_column(String(128), default="")
    signature: Mapped[str] = mapped_column(String(256), default="")
    record_hash: Mapped[str] = mapped_column(String(128), default="")


class SkillListingModel(Base):
    """技能市场挂牌持久化模型。"""

    __tablename__ = "skill_listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    author: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="general")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    price_per_call: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="active")
    quality_score: Mapped[float] = mapped_column(Float, default=0.5)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class SkillReviewModel(Base):
    """技能评价持久化模型。"""

    __tablename__ = "skill_reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id: Mapped[str] = mapped_column(ForeignKey("skill_listings.id"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(256), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class SettlementModel(Base):
    """市场结算持久化模型。"""

    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id: Mapped[str] = mapped_column(ForeignKey("skill_listings.id"), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    platform_fee: Mapped[float] = mapped_column(Float, nullable=False)
    ecosystem_fee: Mapped[float] = mapped_column(Float, nullable=False)
    contributor_payout: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class FeatureFlagModel(Base):
    """Feature Flag 持久化模型（灰度发布）。"""

    __tablename__ = "feature_flags"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    flag_type: Mapped[str] = mapped_column(String(32), nullable=False, default="boolean")
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="disabled")
    value: Mapped[Any] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class ProviderProfileModel(Base):
    """供应方画像 — 可被 AI 雇佣的实体（人/Agent）。

    provider_id 复用 identities 表主键，绑定 Ed25519 身份。
    完整度（is_profile_complete）达标后进入可搜索市场列表。
    """

    __tablename__ = "provider_profiles"

    provider_id: Mapped[str] = mapped_column(ForeignKey("identities.identity_id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="provider")
    headline: Mapped[str] = mapped_column(String(256), nullable=False, server_default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    skills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, server_default="[]")
    categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    city: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    country: Mapped[str] = mapped_column(String(8), nullable=False, server_default="")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    is_remote_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hourly_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    availability: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profile_complete_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_profile_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_bookings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activity_freshness: Mapped[str] = mapped_column(String(32), nullable=False, server_default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class BountyModel(Base):
    """Bounty — AI 雇主发布的物理/数字任务。

    状态机: draft → open → assigned → submitted → work_completed → paid，
    以及 cancelled / disputed（争议冻结）。
    """

    __tablename__ = "bounties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    poster_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    completion_criteria: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    evidence_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    price_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="fixed")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    category: Mapped[str] = mapped_column(String(64), nullable=False, server_default="general")
    skill_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default="[]")
    city: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    country: Mapped[str] = mapped_column(String(8), nullable=False, server_default="")
    is_remote_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    spots_available: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    spots_filled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    identity_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class BountyApplicationModel(Base):
    """Bounty 申请记录。"""

    __tablename__ = "bounty_applications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    bounty_id: Mapped[str] = mapped_column(ForeignKey("bounties.id"), nullable=False, index=True)
    applicant_id: Mapped[str] = mapped_column(
        ForeignKey("provider_profiles.provider_id"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    applied_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


class ReputationModel(Base):
    """信誉分持久化模型 — 实体（Agent/Provider/Skill 作者）的成功率与评价。

    overall_score = 执行 0.4 + 评价 0.3 + 治理 0.2 + 参与 0.1。
    """

    __tablename__ = "reputations"

    entity_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="agent")
    total_actions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    total_reviews: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    peer_reviews: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    governance_participation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    overall_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class TenantModel(Base):
    """租户 — 垂直场景多租户上线的隔离单位。

    每个租户拥有独立的 scene_config（模板/档位/小费/角色集覆盖），
    契约通过 tenant_id 归入租户；运营看板按租户聚合。
    """

    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    scene_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, server_default="{}")
    payout_limit: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    payout_used: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class OutcomeContractModel(Base):
    """成果契约 — 把业务需求翻译为可验收、可定价成果单元的电子合同。

    状态机: draft → open → in_progress → submitted → work_completed → paid，
    以及 disputed（争议）/ cancelled。tier 对应三方案 A/B/C 档位。
    """

    __tablename__ = "outcome_contracts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    contractor_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tier: Mapped[str] = mapped_column(String(16), nullable=False, server_default="balanced")
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    deliverables: Mapped[list[dict]] = mapped_column(JSON, nullable=False, server_default="[]")
    base_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    deposit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deposit_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="held")
    evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    success_rate_commitment: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="draft", index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class ServiceTeamModel(Base):
    """服务团队 — 围绕一份成果契约组合的交付单元（MVP 由平台当项目长）。"""

    __tablename__ = "service_teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(ForeignKey("outcome_contracts.id"), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="assembling")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class ServiceTeamMemberModel(Base):
    """服务团队成员 — 技能作者按 share_ratio 参与成果价分配。"""

    __tablename__ = "service_team_members"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id: Mapped[str] = mapped_column(ForeignKey("service_teams.id"), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default="skill_author")
    share_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


class TipModel(Base):
    """超预期小费 — 需求方在验收超预期时按总价比例打赏，按贡献分配（项目长50% + 技能作者50%）。"""

    __tablename__ = "tips"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(ForeignKey("outcome_contracts.id"), nullable=False, index=True)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    distributions: Mapped[list[dict]] = mapped_column(JSON, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)


class PayoutInstructionModel(Base):
    """出款指令 — 已结算契约的记账凭证，供下游持牌平台执行法币出款。

    不托管真实资金（红线 §9）：本模型仅记录「该付给谁、付多少」的指令，
    实际法币划转由下游持牌支付/身份服务承接。status: pending→executed。
    """

    __tablename__ = "payout_instructions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("outcome_contracts.id"), nullable=False, index=True
    )
    payee_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="contractor")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="CNY")
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="settlement")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    external_ref: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)
