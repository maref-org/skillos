"""Payments webhook API — 持牌平台回执回调（M6-P2）

端点：
  - POST /payments/webhooks/{provider}  持牌平台回执回调（验签 → mark_executed）
  - GET  /payments/providers            当前 provider 与配置状态（只读）
  - POST /payments/contracts/{id}/submit 手动触发出款提交（签名）

红线 §9：本层只回写记账状态，不触碰真实资金。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.market.payments import get_provider, submit_contract_payout
from skillos.market.payments.base import ProviderNotConfiguredError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

_SUPPORTED = {"sandbox", "alipay", "wechat"}


def _resolve_provider(name: str):
    if name not in _SUPPORTED:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")
    return get_provider(name)


@router.get("/providers")
def list_providers():
    """列出支持的 provider 与当前配置状态（只读，供运营排查）。"""
    return {
        "providers": [
            {
                "name": name,
                "configured": _is_configured(name),
                "active": get_provider(name).name,
            }
            for name in sorted(_SUPPORTED)
        ]
    }


@router.post("/webhooks/{provider}")
async def webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_session),
):
    """持牌平台回执回调：验签 → 回写 mark_executed。"""
    p = _resolve_provider(provider)
    raw = await request.body()
    body = _parse_body(raw)
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        receipt = p.verify_webhook(headers, body)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"webhook verification failed: {exc}") from exc

    from skillos.market.payouts import PayoutService

    payouts = PayoutService(db)
    # 回执单号来自 adapter 的平台字段映射（支付宝 out_biz_no / 微信 out_bill_no / sandbox external_ref）
    external_ref = receipt.external_ref
    updated = []
    for instruction_id in receipt.instruction_ids:
        try:
            row = payouts.mark_executed(instruction_id, external_ref=external_ref)
        except ValueError as exc:
            logger.warning("webhook instruction not found: %s", exc)
            continue
        updated.append(
            {
                "instruction_id": row.id,
                "payee_id": row.payee_id,
                "role": row.role,
                "status": row.status,
                "external_ref": row.external_ref,
            }
        )

    return {"success": True, "provider": provider, "updated": updated}


@router.post("/contracts/{contract_id}/submit")
async def submit_contract_payout_api(
    contract_id: str,
    payload: dict = Body(...),
    db: Session = Depends(get_session),
):
    """手动触发出款提交到持牌平台（记账层内部触发为主，此端点为运维手动重试）。"""
    provider_name = payload.get("provider", "")
    try:
        provider = get_provider(provider_name) if provider_name else get_provider()
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        result = submit_contract_payout(db, contract_id, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, **result}


def _parse_body(raw: bytes) -> dict[str, Any]:
    import json

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _is_configured(name: str) -> bool:
    import os

    if name == "sandbox":
        return True
    if name == "alipay":
        return bool(os.environ.get("SKILLOS_ALIPAY_APP_ID")) and bool(os.environ.get("SKILLOS_ALIPAY_PRIVATE_KEY"))
    if name == "wechat":
        return bool(os.environ.get("SKILLOS_WECHAT_MCH_ID")) and bool(os.environ.get("SKILLOS_WECHAT_APIV3_KEY"))
    return False
