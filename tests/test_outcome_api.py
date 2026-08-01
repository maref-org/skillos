"""Tests for Phase C-M2 — outcome contracts API endpoints (Ed25519 signed)."""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.db.models import ReputationModel
from skillos.security.message_signer import MessageSigner
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.outcome import router as outcome_router


def _build_client():
    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(outcome_router)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _build_client()


def _register(client, identity_id):
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
        json={"identity_id": identity_id, "role": "consumer", "public_key_pem": pem},
    )
    assert r.status_code == 200
    return MessageSigner(signer_id=identity_id, private_key=key)


def _signed_post(client, signer, path, payload):
    headers = signer.sign_headers(payload)
    return client.post(path, json=payload, headers=headers)


REQ_TEXT = "给公众号写 30 天内容运营文章并做多平台分发"


def _create_contract(client, requester):
    return _signed_post(
        client,
        requester,
        "/outcome/contracts",
        {"requirement_text": REQ_TEXT},
    )


class TestCreateContract:
    def test_creates_draft_with_three_plans(self, client):
        requester = _register(client, "req-1")
        r = _create_contract(client, requester)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        contract = body["contract"]
        assert contract["status"] == "draft"
        assert contract["requester_id"] == "req-1"
        assert len(body["plans"]) == 3
        tiers = [p["tier"] for p in body["plans"]]
        assert tiers == ["stable", "balanced", "sprint"]
        assert body["plans"][1]["price"] > 0
        assert body["plans"][1]["deposit"] > 0
        assert body["plans"][1]["success_rate"] == 0.85

    def test_rejects_unregistered_signer(self, client):
        signer = MessageSigner(signer_id="ghost")
        r = _signed_post(client, signer, "/outcome/contracts", {"requirement_text": REQ_TEXT})
        assert r.status_code == 403

    def test_rejects_missing_signature(self, client):
        r = client.post("/outcome/contracts", json={"requirement_text": REQ_TEXT})
        assert r.status_code == 401

    def test_validates_min_length(self, client):
        requester = _register(client, "req-2")
        r = _signed_post(client, requester, "/outcome/contracts", {"requirement_text": "ab"})
        assert r.status_code == 422


class TestSelectTier:
    def test_select_tier_opens_contract(self, client):
        requester = _register(client, "req-s1")
        contract = _create_contract(client, requester).json()["contract"]
        cid = contract["id"]
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "sprint"})
        assert r.status_code == 200
        updated = r.json()["contract"]
        assert updated["status"] == "open"
        assert updated["tier"] == "sprint"
        assert updated["deadline"] is not None
        assert updated["success_rate_commitment"] == 0.70

    def test_invalid_tier_rejected(self, client):
        requester = _register(client, "req-s2")
        contract = _create_contract(client, requester).json()["contract"]
        cid = contract["id"]
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "ultra"})
        assert r.status_code == 422

    def test_non_requester_cannot_select(self, client):
        requester = _register(client, "req-s3")
        other = _register(client, "req-s3b")
        contract = _create_contract(client, requester).json()["contract"]
        cid = contract["id"]
        r = _signed_post(client, other, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        assert r.status_code == 403

    def test_select_twice_conflict(self, client):
        requester = _register(client, "req-s4")
        contract = _create_contract(client, requester).json()["contract"]
        cid = contract["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "sprint"})
        assert r.status_code == 409


class TestSignContract:
    def test_contractor_signs_open_contract(self, client):
        requester = _register(client, "req-g1")
        contractor = _register(client, "ctr-g1")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "balanced"})
        r = _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        assert r.status_code == 200
        assert r.json()["contract"]["status"] == "in_progress"
        assert r.json()["contract"]["contractor_id"] == "ctr-g1"


class TestFullLifecycle:
    def test_full_flow_with_tip(self, client):
        requester = _register(client, "req-f1")
        contractor = _register(client, "ctr-f1")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})

        r = _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        assert r.status_code == 200
        assert r.json()["contract"]["status"] == "submitted"

        r = _signed_post(
            client,
            requester,
            f"/outcome/contracts/{cid}/confirm",
            {"accepted": True, "tip_ratio": 0.15},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["contract"]["status"] == "work_completed"
        assert body["tip"]["ratio"] == 0.15
        price = body["contract"]["price"]
        assert abs(body["tip"]["amount"] - round(price * 0.15, 2)) < 0.01

    def test_dispute_flow(self, client):
        requester = _register(client, "req-f2")
        contractor = _register(client, "ctr-f2")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": False})
        assert r.status_code == 200
        assert r.json()["contract"]["status"] == "disputed"

    def test_confirm_before_submit_conflict(self, client):
        requester = _register(client, "req-f3")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": True})
        assert r.status_code == 409

    def test_contractor_cannot_confirm(self, client):
        requester = _register(client, "req-f4")
        contractor = _register(client, "ctr-f4")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        r = _signed_post(client, contractor, f"/outcome/contracts/{cid}/confirm", {"accepted": True})
        assert r.status_code == 403


class TestTip:
    def test_tip_after_completion(self, client):
        requester = _register(client, "req-t1")
        contractor = _register(client, "ctr-t1")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": True})
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/tip", {"ratio": 0.10})
        assert r.status_code == 200
        tip = r.json()["tip"]
        assert tip["requester_id"] == "req-t1"
        assert tip["distributions"][0]["role"] == "lead"
        assert tip["distributions"][0]["member_id"] == "ctr-t1"

    def test_tip_ratio_out_of_range(self, client):
        requester = _register(client, "req-t2")
        contractor = _register(client, "ctr-t2")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": True})
        r = _signed_post(client, requester, f"/outcome/contracts/{cid}/tip", {"ratio": 0.50})
        assert r.status_code == 422


class TestGetContract:
    def test_get_contract_detail(self, client):
        requester = _register(client, "req-get1")
        r = _create_contract(client, requester)
        cid = r.json()["contract"]["id"]
        r = client.get(f"/outcome/contracts/{cid}")
        assert r.status_code == 200
        assert r.json()["contract"]["id"] == cid

    def test_get_missing_contract(self, client):
        r = client.get("/outcome/contracts/ctr-missing")
        assert r.status_code == 404


class TestGetReputation:
    def test_reputation_default_when_no_record(self, client):
        r = client.get("/outcome/reputation/ghost-agent")
        assert r.status_code == 200
        body = r.json()
        assert body["has_record"] is False
        assert body["overall_score"] == 0.0

    def test_reputation_returns_persisted_record(self, client, db_session):
        db_session.add(
            ReputationModel(
                entity_id="prov-1",
                entity_type="provider",
                total_actions=10,
                success_rate=80.0,
                total_reviews=4,
                peer_reviews=90.0,
                governance_participation=2,
                overall_score=85.0,
            )
        )
        db_session.commit()
        r = client.get("/outcome/reputation/prov-1")
        assert r.status_code == 200
        body = r.json()
        assert body["has_record"] is True
        assert body["overall_score"] == 85.0
        assert body["total_actions"] == 10


class TestRiskControls:
    def _disputed(self, client, requester, contractor):
        requester_signer = _register(client, requester)
        contractor_signer = _register(client, contractor)
        cid = _create_contract(client, requester_signer).json()["contract"]["id"]
        _signed_post(client, requester_signer, f"/outcome/contracts/{cid}/select-tier", {"tier": "stable"})
        _signed_post(client, contractor_signer, f"/outcome/contracts/{cid}/sign", {})
        return requester_signer, contractor_signer, cid

    def test_submit_evidence_stored(self, client):
        requester, contractor, cid = self._disputed(client, "req-risk1", "ctr-risk1")
        r = _signed_post(
            client,
            contractor,
            f"/outcome/contracts/{cid}/submit-delivery",
            {"evidence_text": "交付成果：内容策略文档与 30 天日历，合规检查通过"},
        )
        assert r.status_code == 200
        body = r.json()["contract"]
        assert body["evidence_hash"] is not None
        assert body["evidence_risk"] < 0.25
        assert body["status"] == "submitted"

    def test_submit_high_risk_evidence_rejected(self, client):
        requester, contractor, cid = self._disputed(client, "req-risk2", "ctr-risk2")
        r = _signed_post(
            client,
            contractor,
            f"/outcome/contracts/{cid}/submit-delivery",
            {"evidence_text": "报告称成功率 150%，覆盖率 200%，转化率 300%，且引用 https://invalid 数据"},
        )
        assert r.status_code == 409
        assert "failed compliance" in r.json()["detail"]

    def test_arbitrate_approve_flow(self, client):
        requester, contractor, cid = self._disputed(client, "req-risk3", "ctr-risk3")
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": False})
        r = _signed_post(
            client,
            requester,
            f"/outcome/contracts/{cid}/arbitrate",
            {"votes": {"v1": "approve", "v2": "approve", "v3": "approve"}},
        )
        assert r.status_code == 200
        arb = r.json()["arbitration"]
        assert arb["decision"] == "approve"
        assert arb["deposit_status"] == "released"

    def test_arbitrate_reject_forfeits_deposit(self, client):
        requester, contractor, cid = self._disputed(client, "req-risk4", "ctr-risk4")
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": False})
        r = _signed_post(
            client,
            requester,
            f"/outcome/contracts/{cid}/arbitrate",
            {"votes": {"v1": "reject", "v2": "reject", "v3": "reject"}},
        )
        assert r.status_code == 200
        arb = r.json()["arbitration"]
        assert arb["decision"] == "reject"
        assert arb["deposit_status"] == "forfeited"
        assert arb["status"] == "cancelled"

    def test_arbitrate_requires_signature(self, client):
        requester, contractor, cid = self._disputed(client, "req-risk5", "ctr-risk5")
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": False})
        r = client.post(f"/outcome/contracts/{cid}/arbitrate", json={"votes": {"v1": "approve"}})
        assert r.status_code == 401

    def test_full_flow_with_deposit_lifecycle(self, client):
        requester = _register(client, "req-risk6")
        contractor = _register(client, "ctr-risk6")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "balanced"})
        r = client.get(f"/outcome/contracts/{cid}")
        assert r.json()["contract"]["deposit_status"] == "held"
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": True})
        r = client.get(f"/outcome/contracts/{cid}")
        assert r.json()["contract"]["deposit_status"] == "released"


class TestPayoutExport:
    """M5 — 出款指令导出端点（持牌支付桥接层，只读）。"""

    def _paid_contract(self, client, db_session):
        requester = _register(client, "req-payapi")
        contractor = _register(client, "ctr-payapi")
        cid = _create_contract(client, requester).json()["contract"]["id"]
        _signed_post(client, requester, f"/outcome/contracts/{cid}/select-tier", {"tier": "balanced"})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/sign", {})
        _signed_post(client, contractor, f"/outcome/contracts/{cid}/submit-delivery", {})
        _signed_post(client, requester, f"/outcome/contracts/{cid}/confirm", {"accepted": True})
        from skillos.market.outcome_contracts import OutcomeContractService

        svc = OutcomeContractService(db_session)
        svc.create_service_team(cid, "ctr-payapi", [{"member_id": "author-payapi", "share_ratio": 0.4}])
        svc.settle(cid)
        return cid

    def test_manifest_export_after_settle(self, client, db_session):
        cid = self._paid_contract(client, db_session)
        r = client.get(f"/outcome/payouts/{cid}")
        assert r.status_code == 200, r.text
        manifest = r.json()
        assert manifest["contract_id"] == cid
        assert manifest["total_amount"] > 0
        roles = {i["role"] for i in manifest["instructions"]}
        assert roles == {"contractor", "skill_author", "platform"}
        assert any(i["payee_id"] == "ctr-payapi" for i in manifest["instructions"])

    def test_manifest_404_for_missing(self, client):
        r = client.get("/outcome/payouts/ctr-nope")
        assert r.status_code == 404

    def test_manifest_requires_signature_context(self, client, db_session):
        # 未签名 GET 仍可读（只读导出，不要求签名），但契约不存在时应 404
        r = client.get("/outcome/payouts/ctr-nope")
        assert r.status_code == 404


class TestTenantStats:
    """P4.3 — 运营看板：按租户聚合。"""

    @staticmethod
    def _active_tenant(db_session, tenant_id):
        from skillos.market.tenants import TenantService

        tsvc = TenantService(db_session)
        try:
            tsvc.get(tenant_id)
        except ValueError:
            tsvc.create(tenant_id, tenant_id)
        tsvc.set_status(tenant_id, "active")

    def test_aggregates_by_tenant(self, client, db_session):
        from skillos.market.outcome_contracts import OutcomeContractService

        self._active_tenant(db_session, "tenant-a")
        self._active_tenant(db_session, "tenant-b")
        svc = OutcomeContractService(db_session)
        t1 = svc.create("req-t1", "做短视频矩阵", base_price=4000.0, tenant_id="tenant-a")
        svc.select_tier(t1.id, "balanced")
        svc.sign(t1.id, "ctr-t1")
        svc.submit_delivery(t1.id)
        svc.confirm_delivery(t1.id, True)
        svc.settle(t1.id)

        t2 = svc.create("req-t2", "做知识付费专栏", base_price=2000.0, tenant_id="tenant-b")
        svc.select_tier(t2.id, "stable")

        svc.create("req-t3", "写一篇公众号文章", base_price=1000.0)  # default 租户

        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        stats = {s["tenant_id"]: s for s in r.json()["stats"]}
        assert stats["tenant-a"]["contracts"] == 1
        assert stats["tenant-a"]["amount"] > 0
        assert stats["tenant-a"]["completion_rate"] == 1.0
        assert stats["tenant-b"]["contracts"] == 1
        assert stats["tenant-b"]["completion_rate"] == 0.0
        assert stats["default"]["contracts"] == 1
        # default 租户不限额（M9-P1.3）
        assert stats["default"]["payout_limit"] == 0.0
        assert stats["default"]["payout_remaining"] is None

    def test_completion_rate_partial(self, client, db_session):
        from skillos.market.outcome_contracts import OutcomeContractService

        self._active_tenant(db_session, "tenant-c")
        svc = OutcomeContractService(db_session)
        done = svc.create("req-p1", "做内容运营", base_price=3000.0, tenant_id="tenant-c")
        svc.select_tier(done.id, "balanced")
        svc.sign(done.id, "ctr-p1")
        svc.submit_delivery(done.id)
        svc.confirm_delivery(done.id, True)
        svc.settle(done.id)

        cancelled = svc.create("req-p2", "做内容运营", base_price=3000.0, tenant_id="tenant-c")
        svc.select_tier(cancelled.id, "balanced")
        svc.cancel(cancelled.id)

        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        stats = {s["tenant_id"]: s for s in r.json()["stats"]}
        # completion = paid / (paid + cancelled)
        assert stats["tenant-c"]["completion_rate"] == 0.5

    def test_empty_db_returns_empty(self, client):
        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        assert r.json()["stats"] == []

    def test_stats_include_trend(self, client, db_session):
        """stats 含近 N 天趋势折线（向后兼容：stats 聚合保留）。"""
        self._active_tenant(db_session, "tenant-trend")
        from skillos.market.outcome_contracts import OutcomeContractService

        svc = OutcomeContractService(db_session)
        c = svc.create("req-trend", "做内容运营", base_price=3000.0, tenant_id="tenant-trend")
        svc.select_tier(c.id, "balanced")
        svc.sign(c.id, "ctr-trend")
        svc.submit_delivery(c.id)
        svc.confirm_delivery(c.id, True)
        svc.settle(c.id)

        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        body = r.json()
        stats = {s["tenant_id"]: s for s in body["stats"]}
        assert stats["tenant-trend"]["contracts"] == 1
        # trend：近 7 天按日聚合
        assert "trend" in body
        assert "tenant-trend" in body["trend"]
        trend = body["trend"]["tenant-trend"]
        assert isinstance(trend, list)
        assert len(trend) == 7
        today = trend[-1]
        assert today["contracts"] == 1
        assert today["amount"] > 0
        for point in trend[:-1]:
            assert point["contracts"] == 0
            assert point["amount"] == 0.0

    def test_stats_include_contracts_detail(self, client, db_session):
        """stats 含租户契约明细列表（分页）。"""
        self._active_tenant(db_session, "tenant-detail")
        from skillos.market.outcome_contracts import OutcomeContractService

        svc = OutcomeContractService(db_session)
        c = svc.create("req-detail", "做内容运营", base_price=2000.0, tenant_id="tenant-detail")
        svc.select_tier(c.id, "stable")

        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        body = r.json()
        assert "contracts" in body
        assert "tenant-detail" in body["contracts"]
        detail = body["contracts"]["tenant-detail"]
        assert isinstance(detail["items"], list)
        assert len(detail["items"]) == 1
        item = detail["items"][0]
        assert item["id"] == c.id
        assert item["status"] == "open"
        assert item["price"] > 0

    def test_trend_default_points_when_empty(self, client):
        """空库时 trend 仍是近 N 天占位（契约数为 0）。"""
        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        body = r.json()
        assert body["trend"] == {}

    def test_stats_include_payout_quota(self, client, db_session):
        """stats 含租户出款配额字段（default 租户不限额）。"""
        self._active_tenant(db_session, "tenant-quota-s")
        from skillos.market.outcome_contracts import OutcomeContractService
        from skillos.market.tenants import TenantService

        svc = OutcomeContractService(db_session)
        c = svc.create("req-quota-s", "做内容运营", base_price=2000.0, tenant_id="tenant-quota-s")
        svc.select_tier(c.id, "stable")

        tsvc = TenantService(db_session)
        tsvc.set_payout_quota("tenant-quota-s", 5000)
        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        stats = {s["tenant_id"]: s for s in r.json()["stats"]}
        assert stats["tenant-quota-s"]["payout_limit"] == 5000.0
        assert stats["tenant-quota-s"]["payout_used"] == 0.0
        assert stats["tenant-quota-s"]["payout_remaining"] == 5000.0

    def test_stats_include_slo_snapshot(self, client):
        """stats 含 SLO 实时错误预算快照（M9-P2）。"""
        from skillos.kernel.slo import get_slo_manager

        get_slo_manager().record_availability("negmarket_api", True)
        r = client.get("/outcome/tenant-stats")
        assert r.status_code == 200
        body = r.json()
        assert "slo" in body
        assert "negmarket_api" in body["slo"]
        assert "error_budget" in body["slo"]["negmarket_api"]
