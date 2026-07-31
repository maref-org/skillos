from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel
from skillos.market.providers import ProviderRegistry

router = APIRouter(tags=["协议通信"])


def _get_db(db: Session = Depends(get_session)) -> Session:
    return db


def _get_provider_registry(db: Session = Depends(_get_db)) -> ProviderRegistry:
    return ProviderRegistry(db)


@router.get("/protocol/agents")
async def list_agents():
    return {"agents": [], "total": 0}


@router.get("/protocol/identities")
def list_identities(
    role: str | None = Query(None),
    db: Session = Depends(_get_db),
):
    """返回已注册身份（脱敏：不含公钥/私钥全文，仅 identity_id + role + verified）。"""
    q = db.query(IdentityModel)
    identities = q.all()
    result = []
    for identity in identities:
        metadata = identity.metadata_json or {}
        if role and metadata.get("role") != role:
            continue
        result.append(
            {
                "identity_id": identity.identity_id,
                "role": metadata.get("role", ""),
                "verified": bool(metadata.get("verified", False)),
            }
        )
    return {"identities": result, "total": len(result)}


@router.get("/protocol/bridges")
async def list_bridges():
    return {"bridges": [], "total": 0}


@router.get("/protocol/registry/search")
def registry_search(
    query: str = "",
    skill: str | None = Query(None),
    city: str | None = Query(None),
    max_rate: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    registry: ProviderRegistry = Depends(_get_provider_registry),
):
    """委托 ProviderRegistry.search — 搜索可雇佣的供应方。"""
    result = registry.search(
        query=query,
        skill=skill,
        city=city,
        max_rate=max_rate,
        page=page,
        page_size=page_size,
    )
    return {
        "results": [
            {
                "provider_id": p.provider_id,
                "headline": p.headline,
                "skills": p.skills,
                "city": p.city,
                "country": p.country,
                "hourly_rate": p.hourly_rate,
                "currency": p.currency,
                "is_verified": p.is_verified,
                "is_profile_complete": p.is_profile_complete,
                "rating": p.rating,
            }
            for p in result.providers
        ],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }


@router.get("/protocol/providers")
def list_providers(
    city: str | None = Query(None),
    country: str | None = Query(None),
    max_rate: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    registry: ProviderRegistry = Depends(_get_provider_registry),
):
    """可搜索供应方（新增端点）。"""
    result = registry.search(
        city=city,
        country=country,
        max_rate=max_rate,
        page=page,
        page_size=page_size,
    )
    return {
        "providers": [
            {
                "provider_id": p.provider_id,
                "headline": p.headline,
                "city": p.city,
                "hourly_rate": p.hourly_rate,
                "currency": p.currency,
                "is_verified": p.is_verified,
            }
            for p in result.providers
        ],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }
