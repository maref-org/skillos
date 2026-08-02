"""Pools API — 跨租户共享额度池（M11-P2）

端点一览::

    POST /pools                          # 创建共享池（签名）
    GET  /pools                          # 池列表（只读）
    POST /pools/{pool_id}/members        # 添加成员（签名）
    PUT  /pools/{pool_id}/limit          # 调整池限额（签名，pending 审批）
    POST /pools/{pool_id}/adjustments/{id}/approve   # 审批通过（签名）
    POST /pools/{pool_id}/adjustments/{id}/reject    # 审批驳回（签名）
    POST /pools/{pool_id}/release        # 归还借用额度（签名，M12-P2）
    POST /pools/transfer                 # 跨池迁移（签名，M12-P2）
    GET  /pools/{pool_id}                # 池详情（只读）

鉴权: 复用 MessageSigner（Ed25519），可变端点强制签名者身份。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.market.tenant_pools import PoolNotFoundError, TenantPoolService
from skillos.web_api.auth import require_actor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pools", tags=["pools"])


def _get_pool_service(db: Session = Depends(get_session)) -> TenantPoolService:
    return TenantPoolService(db)


async def _require_actor(request: Request, db: Session = Depends(get_session)) -> str:
    """验证请求签名并返回签名者身份 ID（未通过则 401/403）。

    C1 修复：用注册公钥验签（身份-公钥绑定），防止身份冒充。
    """
    return await require_actor(request, db)


@router.post("")
async def create_pool(
    request: Request,
    pool_id: str = Body(..., min_length=3, max_length=64),
    name: str = Body("", max_length=256),
    total_limit: float = Body(0.0, ge=0),
    db: Session = Depends(get_session),
):
    """创建共享额度池。"""
    await _require_actor(request, db)
    service = TenantPoolService(db)
    try:
        pool = service.create(pool_id, name=name, total_limit=total_limit)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "pool": service.serialize(pool)}


@router.get("")
def list_pools(service: TenantPoolService = Depends(_get_pool_service)):
    """共享池列表（只读）。"""
    return {"pools": [service.serialize(p) for p in service.list()]}


@router.get("/{pool_id}")
def get_pool(
    pool_id: str,
    service: TenantPoolService = Depends(_get_pool_service),
):
    """池详情（只读）。"""
    pool = service.get(pool_id)
    if pool is None:
        raise HTTPException(status_code=404, detail=f"Pool not found: {pool_id}")
    return {"pool": service.serialize(pool)}


@router.post("/{pool_id}/members")
async def add_member(
    pool_id: str,
    request: Request,
    tenant_id: str = Body(..., embed=True),
    share_ratio: float = Body(1.0, ge=0, embed=True),
    db: Session = Depends(get_session),
):
    """添加租户到共享池（可借用额度比例）。"""
    await _require_actor(request, db)
    service = TenantPoolService(db)
    try:
        member = service.add_member(pool_id, tenant_id, share_ratio)
    except (PoolNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "tenant_id": member.tenant_id, "share_ratio": member.share_ratio}


@router.put("/{pool_id}/limit")
async def set_limit(
    pool_id: str,
    request: Request,
    new_limit: float = Body(..., ge=0, embed=True),
    db: Session = Depends(get_session),
):
    """调整池限额（创建 pending 审批单）。"""
    requester = await _require_actor(request, db)
    service = TenantPoolService(db)
    try:
        adj = service.set_limit(pool_id, new_limit, requested_by=requester)
    except (PoolNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "adjustment_id": adj.id, "status": adj.status, "new_limit": adj.new_limit}


@router.post("/{pool_id}/adjustments/{adjustment_id}/approve")
async def approve_adjustment(
    pool_id: str,
    adjustment_id: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """审批通过池额度调整（应用 new_limit）。"""
    requester = await _require_actor(request, db)
    service = TenantPoolService(db)
    try:
        adj = service.approve(adjustment_id, approved_by=requester)
    except (PoolNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "adjustment_id": adj.id, "status": adj.status, "pool_id": adj.pool_id}


@router.post("/{pool_id}/adjustments/{adjustment_id}/reject")
async def reject_adjustment(
    pool_id: str,
    adjustment_id: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """审批驳回池额度调整（保持原值）。"""
    requester = await _require_actor(request, db)
    service = TenantPoolService(db)
    try:
        adj = service.reject(adjustment_id, approved_by=requester)
    except (PoolNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "adjustment_id": adj.id, "status": adj.status, "pool_id": adj.pool_id}


@router.post("/{pool_id}/release")
async def release_pool_quota(
    pool_id: str,
    request: Request,
    tenant_id: str = Body(..., embed=True),
    amount: float = Body(..., ge=0, embed=True),
    db: Session = Depends(get_session),
):
    """归还租户从池借用的额度（M12-P2）：池 used 扣减 amount（clamp ≥0）。"""
    await _require_actor(request, db)
    service = TenantPoolService(db)
    if service.get(pool_id) is None:
        raise HTTPException(status_code=404, detail=f"Pool not found: {pool_id}")
    released = service.release(pool_id, tenant_id, amount)
    return {"success": True, "released": released}


@router.post("/transfer")
async def transfer_member(
    request: Request,
    tenant_id: str = Body(..., embed=True),
    to_pool_id: str = Body(..., embed=True),
    share_ratio: float | None = Body(None, ge=0, embed=True),
    db: Session = Depends(get_session),
):
    """跨池迁移（M12-P2）：租户从当前池移入目标池，原成员关系删除。"""
    await _require_actor(request, db)
    service = TenantPoolService(db)
    try:
        service.transfer_member(tenant_id, to_pool_id, share_ratio=share_ratio)
    except PoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rel = service.pool_for_tenant(tenant_id)
    return {"success": True, "tenant_id": tenant_id, "pool_id": rel[0].pool_id if rel else None}
