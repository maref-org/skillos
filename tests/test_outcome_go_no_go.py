"""Tests for M4 — 开放外部 Agent 当项目长（Q2 三方生态）+ 首个真实需求方跑通（Go/No-Go）

端到端验收：真实需求方（企业主，不懂技术）提自然语言需求 → 三方案报价 → 选档 →
外部 Agent 构建者浏览承接当项目长 → 组队技能作者 → 交付（L3 合规）→ 验收+小费 → 结算 → 保证金释放。
"""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.security.message_signer import MessageSigner
from skillos.web_api.agent import router as agent_router
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.outcome import router as outcome_router


def _build_client():
    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(outcome_router)
    app.include_router(agent_router)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _build_client()


def _register(client, identity_id, role="consumer"):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    r = client.post(
        "/onboarding/register",
        json={"identity_id": identity_id, "role": role, "public_key_pem": pem},
    )
    assert r.status_code == 200
    return MessageSigner(signer_id=identity_id, private_key=key)


def _signed_post(client, signer, path, payload):
    headers = signer.sign_headers(payload)
    return client.post(path, json=payload, headers=headers)


REQ = "我要给公司的公众号做 30 天内容运营，写文章并分发到多平台，最后要复盘"


class TestExternalAgentAsProjectLead:
    def test_agent_sees_open_contracts(self, client):
        requester = _register(client, "business-1")
        r = _signed_post(client, requester, "/outcome/contracts", {"requirement_text": REQ})
        cid = r.json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})

        _register(client, "agent-lead-1", role="provider")
        r = client.get("/agent/list_open_contracts")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["contracts"][0]["status"] == "open"
        assert body["contracts"][0]["price"] > 0

    def test_agent_accepts_contract(self, client):
        requester = _register(client, "business-2")
        r = _signed_post(client, requester, "/outcome/contracts", {"requirement_text": REQ})
        cid = r.json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "balanced"})

        agent = _register(client, "agent-lead-2", role="provider")
        r = _signed_post(client, agent, "/agent/accept_contract", {"contract_id": cid})
        assert r.status_code == 200
        contract = r.json()["contract"]
        assert contract["status"] == "in_progress"
        assert contract["contractor_id"] == "agent-lead-2"

    def test_accept_requires_registered_identity(self, client):
        requester = _register(client, "business-3")
        r = _signed_post(client, requester, "/outcome/contracts", {"requirement_text": REQ})
        cid = r.json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})

        ghost = MessageSigner(signer_id="unregistered-agent")
        r = _signed_post(client, ghost, "/agent/accept_contract", {"contract_id": cid})
        assert r.status_code == 403

    def test_agent_lists_own_contracts(self, client):
        requester = _register(client, "business-4")
        agent = _register(client, "agent-lead-4", role="provider")
        cid = _signed_post(client, requester, "/outcome/contracts", {"requirement_text": REQ}).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, agent, "/agent/accept_contract", {"contract_id": cid})

        headers = agent.sign_headers({})
        r = client.get("/agent/list_my_contracts", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["contracts"][0]["contractor_id"] == "agent-lead-4"


class TestRealRequesterGoNoGo:
    """首个真实需求方端到端跑通 — Go/No-Go 验收。"""

    def test_full_loop_go(self, client, db_session):
        from skillos.market.outcome_contracts import OutcomeContractService

        service = OutcomeContractService(db_session=db_session)
        # 1. 需求方（企业主，不懂技术）注册 + 提需求
        business = _register(client, "business-go", role="consumer")
        r = _signed_post(client, business, "/outcome/contracts", {"requirement_text": REQ})
        assert r.status_code == 200
        plans = r.json()["plans"]
        assert len(plans) == 3
        cid = r.json()["contract"]["id"]

        # 2. 需求方在 A/B/C 中选择 B 均衡版（成功率 85%）
        r = _signed_post(client, business, f"/outcome/contracts/{cid}/select-tier", {"tier": "balanced"})
        contract = r.json()["contract"]
        assert contract["success_rate_commitment"] == 0.85
        assert contract["deposit"] > 0
        expected_price = contract["price"]

        # 3. 外部 Agent 构建者浏览可承接契约并承接当项目长
        agent = _register(client, "agent-go", role="provider")
        r = client.get("/agent/list_open_contracts")
        assert r.json()["total"] == 1
        r = _signed_post(client, agent, "/agent/accept_contract", {"contract_id": cid})
        assert r.json()["contract"]["status"] == "in_progress"

        # 4. 项目长组建服务团队（技能作者分成）
        service.create_service_team(
            cid, "agent-go", [{"member_id": "author-go", "role": "skill_author", "share_ratio": 0.4}]
        )

        # 5. 交付（L3 合规证据存证）
        r = _signed_post(
            client,
            agent,
            f"/outcome/contracts/{cid}/submit-delivery",
            {"evidence_text": "已完成 30 天内容日历与 12 篇图文，合规检查通过，无异常引用"},
        )
        assert r.json()["contract"]["status"] == "submitted"
        assert r.json()["contract"]["evidence_hash"] is not None

        # 6. 验收 + 超预期小费
        r = _signed_post(
            client,
            business,
            f"/outcome/contracts/{cid}/confirm",
            {"accepted": True, "tip_ratio": 0.15},
        )
        body = r.json()
        assert body["contract"]["status"] == "work_completed"
        assert body["tip"]["amount"] > 0

        # 7. 结算 + 保证金释放
        settled = service.settle(cid)
        assert settled["amount"] == expected_price
        assert settled["deposit_status"] == "released"
        contract = service.get(cid)
        assert contract.status == "paid"
        assert contract.deposit_status == "released"

        # Go 判定
        assert all(
            [
                contract.status == "paid",
                contract.deposit_status == "released",
                settled["amount"] == expected_price,
            ]
        )

    def test_dispute_arbitration_loop(self, client):
        # 需求方验收不通过 → disputed → 仲裁判 reject → 扣保证金（风险场景闭环）
        business = _register(client, "business-no", role="consumer")
        agent = _register(client, "agent-no", role="provider")
        cid = _signed_post(client, business, "/outcome/contracts", {"requirement_text": REQ}).json()["contract"]["id"]
        _signed_post(client, business, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, agent, "/agent/accept_contract", {"contract_id": cid})
        _signed_post(client, agent, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, business, f"/outcome/contracts/{cid}/confirm", {"accepted": False})
        r = _signed_post(
            client,
            business,
            f"/outcome/contracts/{cid}/arbitrate",
            {"votes": {"v1": "reject", "v2": "reject", "v3": "reject"}},
        )
        arb = r.json()["arbitration"]
        assert arb["decision"] == "reject"
        assert arb["deposit_status"] == "forfeited"
        assert arb["status"] == "cancelled"
