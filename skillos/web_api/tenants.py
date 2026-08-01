"""Tenants API — 租户自助开通（M8-P1.2）

签约方通过签名 API 开通垂直场景租户、更新场景配置、激活场景。
契约创建（/outcome/contracts）对 tenant_id 做存在性 + active 校验。

端点一览::

    POST /tenants                          # 开通租户（签名，幂等）
    GET  /tenants                          # 租户列表（只读）
    GET  /tenants/{tenant_id}              # 租户详情（只读）
    PUT  /tenants/{tenant_id}/scene        # 更新场景配置（签名）
    POST /tenants/{tenant_id}/activate     # 开通场景 draft→active（签名）
    PUT  /tenants/{tenant_id}/quota        # 设置出款限额（签名）

鉴权: 复用 MessageSigner（Ed25519），可变端点强制签名者身份。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel, TenantModel
from skillos.market.tenants import TenantService
from skillos.security.message_signer import MessageSigner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _get_tenant_service(db: Session = Depends(get_session)) -> TenantService:
    return TenantService(db)


async def _require_actor(request: Request, db: Session = Depends(get_session)) -> str:
    """验证请求签名并返回签名者身份 ID（未通过则 401/403）。"""
    raw = await request.body()
    payload: dict[str, Any] = json.loads(raw) if raw else {}
    headers = {k.lower(): v for k, v in request.headers.items()}
    signer_id = headers.get("x-signer-id", "")
    if not signer_id or not MessageSigner.verify(payload, headers):
        raise HTTPException(status_code=401, detail="invalid or missing signature")
    if not db.query(IdentityModel).filter(IdentityModel.identity_id == signer_id).first():
        raise HTTPException(status_code=403, detail="identity not registered")
    return signer_id


def _serialize_tenant(tenant: TenantModel) -> dict[str, Any]:
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "scene_config": tenant.scene_config or {},
        "payout_limit": tenant.payout_limit or 0.0,
        "payout_used": tenant.payout_used or 0.0,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
    }


@router.post("")
async def create_tenant(
    request: Request,
    tenant_id: str = Body(..., min_length=3, max_length=128),
    name: str = Body("", max_length=256),
    scene_config: dict = Body({}),
    db: Session = Depends(get_session),
):
    """开通租户（幂等：已存在则返回现有租户，不报冲突）。"""
    await _require_actor(request, db)
    service = TenantService(db)
    existing = service.get(tenant_id) if _tenant_exists(db, tenant_id) else None
    if existing is not None:
        return {"success": True, "tenant": _serialize_tenant(existing), "created": False}
    tenant = service.create(tenant_id, name=name, scene_config=scene_config)
    return {"success": True, "tenant": _serialize_tenant(tenant), "created": True}


@router.get("")
def list_tenants(service: TenantService = Depends(_get_tenant_service)):
    """租户列表（只读）。"""
    tenants = service.list()
    return {"tenants": [_serialize_tenant(t) for t in tenants]}


@router.get("/{tenant_id}")
def get_tenant(
    tenant_id: str,
    service: TenantService = Depends(_get_tenant_service),
):
    """租户详情（只读）。"""
    try:
        tenant = service.get(tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tenant": _serialize_tenant(tenant)}


@router.put("/{tenant_id}/scene")
async def update_scene(
    tenant_id: str,
    request: Request,
    scene_config: dict = Body(..., embed=True),
    db: Session = Depends(get_session),
):
    """更新租户场景配置（模板/档位/小费/角色集覆盖）。"""
    await _require_actor(request, db)
    service = TenantService(db)
    try:
        tenant = service.update_scene_config(tenant_id, scene_config)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "tenant": _serialize_tenant(tenant)}


@router.post("/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """开通场景：租户状态 draft → active。"""
    await _require_actor(request, db)
    service = TenantService(db)
    try:
        tenant = service.set_status(tenant_id, "active")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "tenant": _serialize_tenant(tenant)}


@router.put("/{tenant_id}/quota")
async def set_quota(
    tenant_id: str,
    request: Request,
    payout_limit: float = Body(..., ge=0, embed=True),
    db: Session = Depends(get_session),
):
    """设置租户出款限额（0 = 不限额）。"""
    await _require_actor(request, db)
    service = TenantService(db)
    try:
        tenant = service.set_payout_quota(tenant_id, payout_limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "tenant": _serialize_tenant(tenant), "usage": service.get_payout_usage(tenant_id)}


def _tenant_exists(db: Session, tenant_id: str) -> bool:
    return db.query(TenantModel).filter(TenantModel.tenant_id == tenant_id).first() is not None
