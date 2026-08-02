"""Agent API — MCP 风格端点（Ed25519 签名鉴权）

对应 RentAHuman /api/keys/register-identity + create_bounty 等 MCP tools。

- 鉴权: MessageSigner 签名头（X-Signer-Id / X-Signature / X-Signature-Timestamp / X-Public-Key）
- 复用: ProviderRegistry / BountyService / RemoteBridge
- 红线（设计文档 §9）: 不托管资金；Bounty 的 poster_id 强制为签名 Agent 挂靠的主体身份

端点一览::

    POST /agent/identities/register-identity   # Agent 注册 Ed25519 身份（免签，首次）
    GET  /agent/search_providers               # 搜索供应方（免费，免签）
    POST /agent/create_bounty                  # 创建 bounty（签名；dry_run 预览）
    POST /agent/accept_application             # 接受申请（签名）
    POST /agent/submit_delivery                # 回传证据（签名）
    POST /agent/confirm_delivery               # 验收确认（签名）
    GET  /agent/list_bounties                  # 查询 bounty（mine 需签名）
    POST /agent/bridges/heartbeat              # 复用 RemoteBridge 心跳（签名）
    POST /agent/bridges/connect                # 桥接连接（签名）
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel
from skillos.market.bounties import BountyService
from skillos.market.outcome_contracts import OutcomeContractService
from skillos.market.providers import ProviderRegistry
from skillos.protocol.remote_control import RemoteBridge
from skillos.web_api.auth import optional_actor, require_actor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent-mcp"])

_bridge = RemoteBridge()

VALID_ROLES = ("provider", "consumer", "both")


def _get_provider_registry(db: Session = Depends(get_session)) -> ProviderRegistry:
    return ProviderRegistry(db)


def _get_bounty_service(db: Session = Depends(get_session)) -> BountyService:
    return BountyService(db)


def _get_outcome_service(db: Session = Depends(get_session)) -> OutcomeContractService:
    return OutcomeContractService(db_session=db)


async def _require_agent(request: Request, db: Session = Depends(get_session)) -> str:
    """验证 Agent 请求签名并返回签名者身份 ID（未通过则 401/403）。

    C1 修复：用注册公钥验签（身份-公钥绑定），防止身份冒充。
    """
    return await require_actor(request, db)


async def _optional_agent(request: Request, db: Session = Depends(get_session)) -> str | None:
    """可选鉴权：带签名头则强制验证，否则返回 None（匿名只读）。"""
    return await optional_actor(request, db)


@router.post("/identities/register-identity")
def register_identity(
    identity_id: str = Body(...),
    role: str = Body("provider"),
    public_key_pem: str | None = Body(None),
    db: Session = Depends(get_session),
):
    """Agent 注册 Ed25519 身份（对应 RentAHuman /api/keys/register-identity）。"""
    if role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
    if db.query(IdentityModel).filter(IdentityModel.identity_id == identity_id).first():
        raise HTTPException(status_code=409, detail=f"Identity already registered: {identity_id}")

    from skillos.web_api.onboarding import _register_identity_and_profile

    try:
        result = _register_identity_and_profile(db, identity_id, role, public_key_pem)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"success": True, **result}


@router.get("/search_providers")
def search_providers(
    skill: str | None = Query(None),
    city: str | None = Query(None),
    max_rate: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    registry: ProviderRegistry = Depends(_get_provider_registry),
):
    """搜索可雇佣供应方（MCP search_providers；市场只读数据免费访问）。"""
    result = registry.search(skill=skill, city=city, max_rate=max_rate, page=page, page_size=page_size)
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
                "rating": p.rating,
            }
            for p in result.providers
        ],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }


@router.post("/create_bounty")
async def create_bounty(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
    service: BountyService = Depends(_get_bounty_service),
):
    """创建 bounty；poster_id 强制为签名 Agent 身份（红线 §9.2）。"""
    payload = dict(payload)
    dry_run = bool(payload.pop("dry_run", False))
    try:
        result = service.create(poster_id=_agent_id, dry_run=dry_run, **payload)
    except (ValueError, TypeError) as exc:
        return {"error": str(exc)}
    if dry_run:
        return result
    return {"success": True, "bounty": result}


@router.post("/accept_application")
async def accept_application(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
    service: BountyService = Depends(_get_bounty_service),
):
    bounty_id = payload.get("bounty_id", "")
    application_id = payload.get("application_id", "")
    try:
        return {"success": True, "bounty": service.accept_application(bounty_id, application_id)}
    except ValueError as exc:
        return {"error": str(exc)}


@router.post("/submit_delivery")
async def submit_delivery(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
    service: BountyService = Depends(_get_bounty_service),
):
    bounty_id = payload.get("bounty_id", "")
    evidence = payload.get("evidence", {})
    try:
        return {"success": True, "bounty": service.submit_delivery(bounty_id, evidence)}
    except ValueError as exc:
        return {"error": str(exc)}


@router.post("/confirm_delivery")
async def confirm_delivery(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
    service: BountyService = Depends(_get_bounty_service),
):
    bounty_id = payload.get("bounty_id", "")
    accepted = bool(payload.get("accepted", True))
    try:
        return {"success": True, "bounty": service.confirm_delivery(bounty_id, accepted)}
    except ValueError as exc:
        return {"error": str(exc)}


@router.get("/list_bounties")
async def list_bounties(
    status: str = Query("open"),
    mine: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _agent_id: str | None = Depends(_optional_agent),
    service: BountyService = Depends(_get_bounty_service),
):
    """查询 bounty；mine=true 需签名身份，仅返回自己发布的。"""
    poster_id = None
    if mine:
        if not _agent_id:
            raise HTTPException(status_code=401, detail="mine=true requires signed request")
        poster_id = _agent_id
    result = service.search(
        status=status, page=page, page_size=page_size, poster_id=poster_id
    )
    return {
        "bounties": result.bounties,
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
    }


def _serialize_contract(contract) -> dict[str, Any]:
    return {
        "id": contract.id,
        "requester_id": contract.requester_id,
        "contractor_id": contract.contractor_id,
        "tier": contract.tier,
        "requirement_text": contract.requirement_text,
        "deliverables": [d.__dict__ for d in contract.deliverables],
        "base_price": contract.base_price,
        "price": contract.price,
        "currency": contract.currency,
        "deposit": contract.deposit,
        "deposit_status": contract.deposit_status,
        "success_rate_commitment": contract.success_rate_commitment,
        "status": contract.status,
        "deadline": contract.deadline.isoformat() if contract.deadline else None,
        "created_at": contract.created_at.isoformat() if contract.created_at else None,
        "updated_at": contract.updated_at.isoformat() if contract.updated_at else None,
    }


@router.post("/contracts/{contract_id}/team")
async def create_team(
    contract_id: str,
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
    service: OutcomeContractService = Depends(_get_outcome_service),
):
    """外部 Agent（contractor）为其承接的契约组队（红线 §8.2：contractor 强制签名身份）。"""
    contract = service.get(contract_id)
    if contract is None:
        return {"error": f"Contract not found: {contract_id}"}
    if contract.contractor_id != _agent_id:
        return {"error": f"only the contractor ({contract.contractor_id}) can create team"}
    members = payload.get("members", [])
    if not members:
        return {"error": "members is required"}
    try:
        team_id = service.create_service_team(contract_id, _agent_id, members)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"success": True, "team_id": team_id}


@router.get("/list_open_contracts")
async def list_open_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: OutcomeContractService = Depends(_get_outcome_service),
):
    """列出可承接的 open 契约（外部 Agent 构建者浏览项目长机会，免费只读）。"""
    rows = service.list_open(page=page, page_size=page_size)
    return {
        "contracts": [_serialize_contract(c) for c in rows],
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }


@router.post("/accept_contract")
async def accept_contract(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
    service: OutcomeContractService = Depends(_get_outcome_service),
):
    """外部 Agent 承接 open 契约成为项目长（contractor = 签名 Agent 身份，红线 §8.2）。"""
    contract_id = payload.get("contract_id", "")
    if not contract_id:
        return {"error": "contract_id is required"}
    try:
        updated = service.sign(contract_id, _agent_id)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"success": True, "contract": _serialize_contract(updated)}


@router.get("/list_my_contracts")
async def list_my_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _agent_id: str = Depends(_require_agent),
    service: OutcomeContractService = Depends(_get_outcome_service),
):
    """列出当前 Agent 作为项目长承接的成果契约。"""
    rows = service.list_by_contractor(_agent_id, page=page, page_size=page_size)
    return {
        "contracts": [_serialize_contract(c) for c in rows],
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }


@router.post("/bridges/heartbeat")
async def bridge_heartbeat(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
):
    """复用 RemoteBridge 心跳通道。"""
    ok = await _bridge.update_heartbeat(payload.get("session_id", ""))
    return {"success": ok, "session_id": payload.get("session_id", "")}


@router.post("/bridges/connect")
async def bridge_connect(
    payload: dict = Body(...),
    _agent_id: str = Depends(_require_agent),
):
    """复用 RemoteBridge 桥接连接通道。"""
    try:
        result = await _bridge.connect_bridge(
            payload.get("session_id", ""),
            payload.get("remote_url", ""),
            payload.get("api_key", ""),
        )
        return {"success": True, **result}
    except ValueError as exc:
        return {"error": str(exc)}
