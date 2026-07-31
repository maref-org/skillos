"""Onboarding — 供应方（Provider）身份注册与画像补全 API

流程：
  1. POST /onboarding/register   — 注册 Ed25519 身份（同时创建供应方画像骨架）
  2. POST /onboarding/verify     — challenge-response 身份验证 → is_verified
  3. POST /onboarding/profile    — 补全画像（技能/位置/定价/可用性）
  4. GET  /onboarding/profile/{provider_id}/completeness — 完整度进度条

安全红线：不托管私钥/真实资金；角色仅 provider/consumer/both。
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel
from skillos.market.providers import ProviderProfile, ProviderRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

VALID_ROLES = ("provider", "consumer", "both")


def _get_provider_registry(db: Session = Depends(get_session)) -> ProviderRegistry:
    return ProviderRegistry(db)


@router.post("/register")
def register(
    identity_id: str = Body(..., min_length=3, max_length=128),
    role: str = Body("provider"),
    public_key_pem: str | None = Body(None, description="可选；不传则由服务端生成密钥对"),
    db: Session = Depends(get_session),
):
    """注册 Ed25519 身份并创建供应方画像骨架。"""
    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
    if public_key_pem:
        try:
            serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid Ed25519 public key PEM: {exc}") from exc
    try:
        result = _register_identity_and_profile(db, identity_id, role, public_key_pem)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, **result}


def _register_identity_and_profile(
    db: Session,
    identity_id: str,
    role: str = "provider",
    public_key_pem: str | None = None,
) -> dict:
    """注册 Ed25519 身份并创建供应方画像骨架（供 onboarding 与 agent API 复用）。"""
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}")
    if db.query(IdentityModel).filter(IdentityModel.identity_id == identity_id).first():
        raise ValueError(f"Identity already registered: {identity_id}")

    if public_key_pem:
        try:
            serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        except Exception as exc:
            raise ValueError(f"Invalid Ed25519 public key PEM: {exc}") from exc
    else:
        private_key = Ed25519PrivateKey.generate()
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        logger.warning("Onboarding generated keypair for %s; private key is not stored", identity_id)

    now = datetime.now(timezone.utc)
    identity = IdentityModel(
        identity_id=identity_id,
        public_key_pem=public_key_pem,
        metadata_json={"role": role, "verified": False},
        created_at=now,
        updated_at=now,
    )
    db.add(identity)
    db.flush()

    registry = ProviderRegistry(db)
    profile = registry.create_profile(identity_id, role=role)
    return {
        "identity_id": identity_id,
        "role": role,
        "public_key_pem": public_key_pem,
        "profile": _serialize_profile(profile),
    }


@router.post("/verify")
def verify(
    identity_id: str = Body(...),
    challenge: str = Body(...),
    challenge_signature: str = Body(...),
    db: Session = Depends(get_session),
):
    """challenge-response 身份验证：客户端用私钥签名 challenge，服务端验签。"""
    identity = db.query(IdentityModel).filter(IdentityModel.identity_id == identity_id).first()
    if identity is None:
        raise HTTPException(status_code=404, detail=f"Identity not found: {identity_id}")

    try:
        public_key: Ed25519PublicKey = serialization.load_pem_public_key(
            identity.public_key_pem.encode("utf-8")
        )

        public_key.verify(base64.b64decode(challenge_signature), challenge.encode("utf-8"))
    except Exception as exc:
        logger.warning("Identity verification failed for %s: %s", identity_id, exc)
        raise HTTPException(status_code=400, detail="invalid_signature") from exc

    metadata = dict(identity.metadata_json or {})
    metadata["verified"] = True
    identity.metadata_json = metadata
    db.flush()

    registry = ProviderRegistry(db)
    profile = registry.verify(identity_id)
    return {
        "success": True,
        "identity_id": identity_id,
        "verified": True,
        "profile": _serialize_profile(profile),
    }


@router.post("/profile")
def update_profile(
    provider_id: str = Body(...),
    profile: dict = Body(...),
    registry: ProviderRegistry = Depends(_get_provider_registry),
):
    """创建/更新供应方画像（headline/bio/categories + skills + 位置 + 定价 + 可用性）。"""
    if not registry.get_profile(provider_id):
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")

    try:
        _apply_profile_update(registry, provider_id, profile)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"success": True, "profile": _serialize_profile(registry.get_profile(provider_id))}


def _apply_profile_update(registry: ProviderRegistry, provider_id: str, profile: dict) -> None:
    """将画像更新字段应用到 ProviderRegistry（供端点复用，内部做字段分发）。"""
    basic = {
        k: profile[k]
        for k in ("headline", "bio", "categories", "gender", "phone")
        if k in profile
    }
    if basic:
        registry.update_profile(provider_id, basic)

    for skill in profile.get("skills", []):
        registry.add_skill(
            provider_id,
            skill["skill_id"],
            proficiency=skill.get("proficiency", 0.5),
            category=skill.get("category", "general"),
        )

    if any(k in profile for k in ("city", "country", "timezone", "is_remote_available")):
        registry.set_location(
            provider_id,
            city=profile.get("city", ""),
            country=profile.get("country", ""),
            timezone=profile.get("timezone", ""),
            is_remote_available=bool(profile.get("is_remote_available", False)),
        )

    if any(k in profile for k in ("hourly_rate", "currency")):
        registry.set_pricing(
            provider_id,
            hourly_rate=float(profile.get("hourly_rate", 0.0)),
            currency=profile.get("currency", "CNY"),
        )

    if "availability" in profile:
        registry.set_availability(provider_id, profile.get("availability", {}))


@router.get("/profile/{provider_id}/completeness")
def profile_completeness(
    provider_id: str,
    registry: ProviderRegistry = Depends(_get_provider_registry),
):
    """完整度进度条 + 缺失字段。"""
    if not registry.get_profile(provider_id):
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_id}")
    return registry.compute_completeness(provider_id)


def _serialize_profile(profile: ProviderProfile) -> dict:
    return {
        "provider_id": profile.provider_id,
        "role": profile.role,
        "headline": profile.headline,
        "skills": profile.skills,
        "city": profile.city,
        "country": profile.country,
        "hourly_rate": profile.hourly_rate,
        "currency": profile.currency,
        "is_verified": profile.is_verified,
        "profile_complete_score": profile.profile_complete_score,
        "is_profile_complete": profile.is_profile_complete,
    }
