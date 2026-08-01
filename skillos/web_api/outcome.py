"""Outcome Contracts API — 成果契约闭环（M2）

端点一览::

    POST /outcome/contracts                     # 提需求 + 返回三方案（签名，requester 身份）
    POST /outcome/contracts/{id}/select-tier    # 选档签约（签名，requester）
    POST /outcome/contracts/{id}/sign           # 项目长签约开工（签名，contractor）
    POST /outcome/contracts/{id}/submit-delivery # 提交交付（签名，contractor）
    POST /outcome/contracts/{id}/confirm        # 验收（签名，requester；含小费选项）
    POST /outcome/contracts/{id}/tip            # 超预期小费（签名，requester）
    GET  /outcome/contracts/{id}                # 契约详情/证据链（只读）
    GET  /outcome/reputation/{entity_id}        # 信誉分查询（只读）

鉴权: 复用 MessageSigner（Ed25519）签名头（X-Signer-Id / X-Signature / X-Signature-Timestamp / X-Public-Key）。
红线（设计文档 §8）:
  - 契约方强制为签名身份，AI 不独立缔约（requester 必须是已注册的碳基/挂靠主体）。
  - 不托管真实资金：deposit 为履约保证金记账字段，法币支付由下游持牌平台承接。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel, OutcomeContractModel, ReputationModel
from skillos.kernel.slo import get_slo_manager
from skillos.market.outcome_contracts import (
    OutcomeContract,
    OutcomeContractService,
    OutcomeContractStatus,
    QuotePlan,
    Tip,
)
from skillos.market.payouts import PayoutService
from skillos.market.tenants import TenantService
from skillos.security.message_signer import MessageSigner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outcome", tags=["outcome"])

VALID_TIERS = ("stable", "balanced", "sprint")


def _get_service(db: Session = Depends(get_session)) -> OutcomeContractService:
    return OutcomeContractService(db_session=db)


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


def _serialize_contract(contract: OutcomeContract) -> dict[str, Any]:
    return {
        "id": contract.id,
        "requester_id": contract.requester_id,
        "contractor_id": contract.contractor_id,
        "tenant_id": contract.tenant_id,
        "tier": contract.tier,
        "requirement_text": contract.requirement_text,
        "deliverables": [d.__dict__ for d in contract.deliverables],
        "base_price": contract.base_price,
        "price": contract.price,
        "currency": contract.currency,
        "deposit": contract.deposit,
        "deposit_status": contract.deposit_status,
        "evidence_hash": contract.evidence_hash,
        "evidence_risk": contract.evidence_risk,
        "success_rate_commitment": contract.success_rate_commitment,
        "status": contract.status,
        "deadline": contract.deadline.isoformat() if contract.deadline else None,
        "created_at": _iso(contract.created_at),
        "updated_at": _iso(contract.updated_at),
    }


def _serialize_plan(plan: QuotePlan) -> dict[str, Any]:
    return {
        "tier": plan.tier,
        "label": plan.label,
        "description": plan.description,
        "success_rate": plan.success_rate,
        "price": plan.price,
        "delivery_days": plan.delivery_days,
        "deposit": plan.deposit,
    }


def _serialize_tip(tip: Tip) -> dict[str, Any]:
    return {
        "id": tip.id,
        "contract_id": tip.contract_id,
        "requester_id": tip.requester_id,
        "amount": tip.amount,
        "ratio": tip.ratio,
        "distributions": tip.distributions,
        "created_at": _iso(tip.created_at),
    }


def _iso(dt: datetime) -> str:
    return dt.isoformat() if dt else None


@router.post("/contracts")
async def create_contract(
    request: Request,
    requirement_text: str = Body(..., min_length=5, max_length=2000),
    base_price: float | None = Body(None, ge=0),
    tenant_id: str | None = Body(None, max_length=128),
    db: Session = Depends(get_session),
):
    """提需求 → 创建契约草稿并返回三方案报价（A/B/C）。可选 tenant_id 归入租户（须 active）。"""
    requester_id = await _require_actor(request, db)
    service = OutcomeContractService(db_session=db)
    try:
        contract = service.create(requester_id, requirement_text, base_price, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plans = service.generate_plans(requirement_text, contract.base_price)
    return {
        "success": True,
        "contract": _serialize_contract(contract),
        "plans": [_serialize_plan(p) for p in plans],
    }


@router.post("/contracts/{contract_id}/select-tier")
async def select_tier(
    contract_id: str,
    request: Request,
    tier: str = Body(..., embed=True),
    db: Session = Depends(get_session),
):
    """选档签约（draft → open）。"""
    requester_id = await _require_actor(request, db)
    if tier not in VALID_TIERS:
        raise HTTPException(status_code=422, detail=f"tier must be one of {VALID_TIERS}")
    service = OutcomeContractService(db_session=db)
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    if contract.requester_id != requester_id:
        raise HTTPException(status_code=403, detail="only the requester can select tier")
    try:
        updated = service.select_tier(contract_id, tier)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "contract": _serialize_contract(updated)}


@router.post("/contracts/{contract_id}/sign")
async def sign_contract(
    contract_id: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """项目长签约开工（open → in_progress）。contractor 为签名者身份。"""
    contractor_id = await _require_actor(request, db)
    service = OutcomeContractService(db_session=db)
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    try:
        updated = service.sign(contract_id, contractor_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "contract": _serialize_contract(updated)}


@router.post("/contracts/{contract_id}/submit-delivery")
async def submit_delivery(
    contract_id: str,
    request: Request,
    evidence_text: str = Body("", max_length=20000, embed=True),
    db: Session = Depends(get_session),
):
    """项目长提交交付（in_progress → submitted）。交付证据强制过 L3 合规检查。"""
    contractor_id = await _require_actor(request, db)
    service = OutcomeContractService(db_session=db)
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    if contract.contractor_id != contractor_id:
        raise HTTPException(status_code=403, detail="only the contractor can submit delivery")
    try:
        updated = service.submit_delivery(contract_id, evidence_text=evidence_text)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "contract": _serialize_contract(updated)}


@router.post("/contracts/{contract_id}/confirm")
async def confirm_delivery(
    contract_id: str,
    request: Request,
    accepted: bool = Body(...),
    tip_ratio: float | None = Body(None, ge=0.10, le=0.20),
    db: Session = Depends(get_session),
):
    """需求方验收（submitted → work_completed / disputed）。接受时可附带超预期小费。"""
    requester_id = await _require_actor(request, db)
    service = OutcomeContractService(db_session=db)
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    if contract.requester_id != requester_id:
        raise HTTPException(status_code=403, detail="only the requester can confirm delivery")
    try:
        updated = service.confirm_delivery(contract_id, accepted)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result: dict[str, Any] = {"success": True, "contract": _serialize_contract(updated)}
    if accepted and tip_ratio is not None:
        try:
            tip = service.add_tip(contract_id, requester_id, tip_ratio)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result["tip"] = _serialize_tip(tip)
    return result


@router.post("/contracts/{contract_id}/tip")
async def add_tip(
    contract_id: str,
    request: Request,
    ratio: float = Body(..., ge=0.10, le=0.20, embed=True),
    db: Session = Depends(get_session),
):
    """超预期小费（work_completed 之后，比例 10%~20%）。"""
    requester_id = await _require_actor(request, db)
    service = OutcomeContractService(db_session=db)
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    try:
        tip = service.add_tip(contract_id, requester_id, ratio)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, "tip": _serialize_tip(tip)}


@router.post("/contracts/{contract_id}/arbitrate")
async def arbitrate(
    contract_id: str,
    request: Request,
    votes: dict[str, str] = Body(..., embed=True),
    db: Session = Depends(get_session),
):
    """L4 仲裁：disputed 争议由验证节点投票走拜占庭共识（approve/reject）。"""
    await _require_actor(request, db)
    service = OutcomeContractService(db_session=db)
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    try:
        result = service.arbitrate(contract_id, votes)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "arbitration": result}


@router.get("/contracts/{contract_id}")
def get_contract(
    contract_id: str,
    service: OutcomeContractService = Depends(_get_service),
):
    """契约详情（只读）。"""
    contract = service.get(contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
    tips = [_serialize_tip(t) for t in service.get_tips(contract_id)]
    return {"contract": _serialize_contract(contract), "tips": tips}


@router.get("/payouts/{contract_id}")
def get_payout_manifest(
    contract_id: str,
    db: Session = Depends(get_session),
):
    """导出契约出款指令 manifest（只读；实际法币由下游持牌平台执行）。"""
    payouts = PayoutService(db)
    try:
        manifest = payouts.export_manifest(contract_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return manifest


def _payout_usage(db: Session, tenant_id: str) -> dict[str, Any]:
    """取租户出款配额使用情况；default/未知租户返回 0（不限额）。

    键名统一为 payout_limit/payout_used/payout_remaining（与 tenants API 序列化一致）。
    """
    if tenant_id == "default":
        return {"payout_limit": 0.0, "payout_used": 0.0, "payout_remaining": None}
    try:
        usage = TenantService(db).get_payout_usage(tenant_id)
        return {
            "payout_limit": usage["limit"],
            "payout_used": usage["used"],
            "payout_remaining": usage["remaining"],
        }
    except ValueError:
        return {"payout_limit": 0.0, "payout_used": 0.0, "payout_remaining": None}


@router.get("/tenant-stats")
def get_tenant_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_session),
):
    """运营看板：按租户聚合契约数/成交额/完成率/平均交付周期 + 趋势 + 明细（只读）。

    租户为空归入 "default"。completion_rate = paid / (paid + cancelled)。
    trend: 近 `days` 天按日聚合的契约数/成交额折线（看板趋势图）。
    contracts: 各租户契约明细分页（id/状态/金额/创建时间）。
    stats[]: 各租户配额（payout_limit/payout_used/payout_remaining）。
    slo: SLOManager 实时错误预算快照（M9-P2）。
    """
    rows = db.query(OutcomeContractModel).all()
    buckets: dict[str, list[OutcomeContractModel]] = {}
    for r in rows:
        key = r.tenant_id or "default"
        buckets.setdefault(key, []).append(r)

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    trend: dict[str, list[dict[str, Any]]] = {}
    details: dict[str, dict[str, Any]] = {}
    stats = []
    for tenant_id, contracts in sorted(buckets.items()):
        paid = [c for c in contracts if c.status == OutcomeContractStatus.PAID]
        cancelled = [c for c in contracts if c.status == OutcomeContractStatus.CANCELLED]
        denominator = len(paid) + len(cancelled)
        total_days = 0.0
        with_dates = 0
        for c in paid:
            if c.created_at and c.updated_at:
                total_days += (c.updated_at - c.created_at).total_seconds() / 86400.0
                with_dates += 1
        stats.append(
            {
                "tenant_id": tenant_id,
                "contracts": len(contracts),
                "amount": round(sum(c.price for c in contracts), 2),
                "completion_rate": round(len(paid) / denominator, 4) if denominator else 0.0,
                "paid": len(paid),
                "cancelled": len(cancelled),
                "avg_delivery_days": round(total_days / with_dates, 2) if with_dates else None,
                **_payout_usage(db, tenant_id),
            }
        )

        # 趋势折线：近 N 天按日聚合契约数与成交额
        buckets_by_day: dict[str, dict[str, Any]] = {}
        for c in contracts:
            day = c.created_at.strftime("%Y-%m-%d") if c.created_at else today.strftime("%Y-%m-%d")
            b = buckets_by_day.setdefault(day, {"contracts": 0, "amount": 0.0})
            b["contracts"] += 1
            b["amount"] += c.price
        points = []
        for offset in range(days - 1, -1, -1):
            day = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
            b = buckets_by_day.get(day, {"contracts": 0, "amount": 0.0})
            points.append({"date": day, "contracts": b["contracts"], "amount": round(b["amount"], 2)})
        trend[tenant_id] = points

        # 契约明细（id/状态/金额/创建时间，按创建时间倒序）
        items = [
            {
                "id": c.id,
                "status": c.status,
                "tier": c.tier,
                "price": c.price,
                "created_at": _iso(c.created_at),
            }
            for c in sorted(contracts, key=lambda x: x.created_at or today, reverse=True)
        ]
        details[tenant_id] = {"total": len(items), "items": items}

    slo = get_slo_manager().get_slo_summary()

    return {"stats": stats, "trend": trend, "contracts": details, "slo": slo}


@router.get("/reputation/{entity_id}")
def get_reputation(
    entity_id: str,
    db: Session = Depends(get_session),
):
    """信誉分查询（只读）。返回持久化的 ReputationModel，无记录时返回默认中值。"""
    row = db.query(ReputationModel).filter(ReputationModel.entity_id == entity_id).first()
    if row is None:
        return {
            "entity_id": entity_id,
            "entity_type": "agent",
            "total_actions": 0,
            "success_rate": 0.0,
            "total_reviews": 0,
            "peer_reviews": 0.0,
            "governance_participation": 0,
            "overall_score": 0.0,
            "has_record": False,
        }
    return {
        "entity_id": row.entity_id,
        "entity_type": row.entity_type,
        "total_actions": row.total_actions,
        "success_rate": row.success_rate,
        "total_reviews": row.total_reviews,
        "peer_reviews": row.peer_reviews,
        "governance_participation": row.governance_participation,
        "overall_score": row.overall_score,
        "has_record": True,
    }
