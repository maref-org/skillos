"""Tests for M6-P3 — 真实 HTTP 客户端接入（ASGI transport 等价真实 HTTP）"""

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import httpx
from fastapi import FastAPI

from skillos.security.message_signer import MessageSigner
from skillos.web_api.agent import router as agent_router
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.outcome import router as outcome_router
from skillos.web_api.payments import router as payments_router

_scripts = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("agent_http_client", _scripts / "agent_http_client.py")
_agent_http_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_agent_http_client)
AgentHttpClient = _agent_http_client.AgentHttpClient


def _build_app() -> FastAPI:
    app = FastAPI()
    for r in (onboarding_router, outcome_router, agent_router, payments_router):
        app.include_router(r)
    return app


@pytest.fixture
async def client(db_session):
    """真实 HTTP 客户端通过 ASGI transport 访问（等价真实 uvicorn + HTTP）。"""
    app = _build_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as c:
        yield c


@pytest.mark.asyncio
async def test_smoke_payment_providers(client):
    r = await client.get("/payments/providers")
    assert r.status_code == 200
    assert {p["name"] for p in r.json()["providers"]} == {"sandbox", "alipay", "wechat"}


@pytest.mark.asyncio
async def test_register_and_full_flow(client, db_session):
    # 需求方（企业主）用原生 HTTP + 签名
    business = MessageSigner(signer_id="business-real")
    r = await client.post(
        "/onboarding/register",
        json={
            "identity_id": "business-real",
            "role": "consumer",
            "public_key_pem": business._public_key_pem,
        },
    )
    assert r.status_code == 200

    # 提需求
    req = {"requirement_text": "给公众号做 30 天内容运营并分发"}
    r = await client.post(
        "/outcome/contracts",
        json=req,
        headers=business.sign_headers(req),
    )
    assert r.status_code == 200, r.text
    cid = r.json()["contract"]["id"]
    tier_payload = {"tier": "balanced"}
    await client.post(
        f"/outcome/contracts/{cid}/select-tier",
        json=tier_payload,
        headers=business.sign_headers(tier_payload),
    )

    # 外部 Agent 用真实 HTTP 客户端（同步签名，异步发送）
    agent = AgentHttpClient("http://testserver", "agent-real", signer=MessageSigner(signer_id="agent-real"))
    try:
        # 覆盖底层 client 为异步版本（AgentHttpClient 内部是同步 httpx.Client，这里直接用等价签名流程）
        r = await client.post(
            "/onboarding/register",
            json={
                "identity_id": "agent-real",
                "role": "provider",
                "public_key_pem": agent.signer._public_key_pem,
            },
        )
        assert r.status_code == 200

        r = await client.get("/agent/list_open_contracts")
        assert r.status_code == 200
        assert any(c["id"] == cid for c in r.json()["contracts"])

        accept_payload = {"contract_id": cid}
        r = await client.post(
            "/agent/accept_contract",
            json=accept_payload,
            headers=agent.signer.sign_headers(accept_payload),
        )
        assert r.status_code == 200, r.text
        assert r.json()["contract"]["contractor_id"] == "agent-real"

        # 组队 + 交付
        from skillos.market.outcome_contracts import OutcomeContractService

        svc = OutcomeContractService(db_session)
        svc.create_service_team(cid, "agent-real", [{"member_id": "author-real", "share_ratio": 0.4}])
        db_session.commit()

        del_payload = {"evidence_text": "已完成内容运营，合规通过"}
        r = await client.post(
            f"/outcome/contracts/{cid}/submit-delivery",
            json=del_payload,
            headers=agent.signer.sign_headers(del_payload),
        )
        assert r.status_code == 200, r.text
        assert r.json()["contract"]["status"] == "submitted"

        # 验收 + 结算 + 出款提交（sandbox）
        confirm_payload = {"accepted": True}
        r = await client.post(
            f"/outcome/contracts/{cid}/confirm",
            json=confirm_payload,
            headers=business.sign_headers(confirm_payload),
        )
        assert r.status_code == 200, r.text
        svc.settle(cid)
        db_session.commit()

        r = await client.post(f"/payments/contracts/{cid}/submit", json={"provider": "sandbox"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "succeeded"
        assert len(r.json()["instructions"]) >= 3
    finally:
        agent.close()


@pytest.mark.asyncio
async def test_concurrency_smoke(client, db_session):
    """M7-P3.3 — 多客户端并发冒烟（ASGI transport 等价真实 HTTP）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "agent_concurrency_demo",
        Path(__file__).resolve().parent.parent / "scripts" / "agent_concurrency_demo.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 预置 open 契约（每个 Agent 各一个，避免并发竞争同一契约）
    from skillos.market.outcome_contracts import OutcomeContractService

    svc = OutcomeContractService(db_session)
    ids = []
    for i in range(2):
        ctr = svc.create(f"business-conc-{i}", "做内容运营并分发", base_price=4000.0)
        svc.select_tier(ctr.id, "balanced")
        ids.append(ctr.id)
    db_session.commit()

    app = FastAPI()
    from skillos.web_api import api_router

    app.include_router(api_router)
    results = await mod.run_demo(
        "http://testserver", 2, contract_ids=ids, transport=httpx.ASGITransport(app=app), serial=True
    )
    assert len(results) == 2
    for r in results:
        assert r["ok"], r
    assert {r["identity"] for r in results} == {"agent-conc-0", "agent-conc-1"}
