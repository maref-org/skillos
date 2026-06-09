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

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
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
