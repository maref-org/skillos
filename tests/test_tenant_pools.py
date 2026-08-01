"""Tests for M11-P2 — 跨租户共享额度池

覆盖：建池/成员/联合限额校验/审批流/API。
"""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.market.outcome_contracts import OutcomeContractService, Tier
from skillos.market.payouts import PayoutLimitExceededError, PayoutService
from skillos.market.tenant_pools import TenantPoolService
from skillos.market.tenants import TenantService
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.pools import router as pools_router


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(pools_router)
    return TestClient(app)


class TestTenantPoolService:
    def test_create_and_get(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-1", name="平台池", total_limit=50000)
        pool = svc.get("pool-1")
        assert pool is not None
        assert pool.total_limit == 50000
        assert pool.used == 0.0

    def test_create_negative_rejected(self, db_session):
        svc = TenantPoolService(db_session)
        with pytest.raises(ValueError, match="negative"):
            svc.create("pool-neg", total_limit=-1)

    def test_add_member(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-m", total_limit=10000)
        m = svc.add_member("pool-m", "tenant-a", share_ratio=0.5)
        assert m.tenant_id == "tenant-a"
        assert m.share_ratio == 0.5

    def test_check_available_share(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-s", total_limit=10000)
        svc.add_member("pool-s", "tenant-a", share_ratio=0.3)
        svc.add_member("pool-s", "tenant-b", share_ratio=0.7)
        assert svc.check_available("pool-s", "tenant-a") == pytest.approx(3000.0)
        assert svc.check_available("pool-s", "tenant-b") == pytest.approx(7000.0)

    def test_consume_reduces_remaining(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-c", total_limit=10000)
        svc.add_member("pool-c", "tenant-a", share_ratio=0.5)
        assert svc.consume("pool-c", "tenant-a", 4000) is True
        pool = svc.get("pool-c")
        assert pool.used == 4000.0
        assert svc.check_available("pool-c", "tenant-a") == pytest.approx(3000.0)

    def test_consume_over_share_rejected(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-o", total_limit=10000)
        svc.add_member("pool-o", "tenant-a", share_ratio=0.2)
        assert svc.consume("pool-o", "tenant-a", 5000) is False

    def test_non_member_cannot_consume(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-n", total_limit=10000)
        assert svc.consume("pool-n", "tenant-x", 100) is False


class TestPoolAdjustmentWorkflow:
    def test_set_limit_creates_pending(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-w", total_limit=5000)
        adj = svc.set_limit("pool-w", 8000, requested_by="ops")
        assert adj.status == "pending"
        assert adj.new_limit == 8000
        # 未审批前池值不变
        assert svc.get("pool-w").total_limit == 5000

    def test_approve_applies_limit(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-wa", total_limit=5000)
        adj = svc.set_limit("pool-wa", 9000, requested_by="ops")
        approved = svc.approve(adj.id, approved_by="auditor")
        assert approved.status == "approved"
        assert svc.get("pool-wa").total_limit == 9000

    def test_reject_keeps_old_limit(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-wr", total_limit=5000)
        adj = svc.set_limit("pool-wr", 9000, requested_by="ops")
        rejected = svc.reject(adj.id, approved_by="auditor")
        assert rejected.status == "rejected"
        assert svc.get("pool-wr").total_limit == 5000

    def test_double_approve_rejected(self, db_session):
        svc = TenantPoolService(db_session)
        svc.create("pool-wd", total_limit=5000)
        adj = svc.set_limit("pool-wd", 9000)
        svc.approve(adj.id)
        with pytest.raises(ValueError, match="not pending"):
            svc.approve(adj.id)


class TestPoolIntegrationWithPayouts:
    def _paid_contract(self, db_session, requester, tenant_id, price=5000.0):
        svc = OutcomeContractService(db_session)
        ctr = svc.create(requester, "做内容全流程", base_price=price)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        svc.create_service_team(
            ctr.id, "ctr-pool", [{"member_id": "author-pool", "role": "skill_author", "share_ratio": 0.4}]
        )
        ctr = svc.sign(ctr.id, "ctr-pool")
        ctr = svc.submit_delivery(ctr.id)
        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        svc.settle(ctr.id)
        from skillos.db.models import OutcomeContractModel

        model = db_session.query(OutcomeContractModel).filter(OutcomeContractModel.id == ctr.id).first()
        model.tenant_id = tenant_id
        db_session.flush()
        return ctr.id

    def test_payout_borrows_from_pool_when_own_over(self, db_session):
        # 租户自有额度 3000，契约 5000 → 超自有，从池借用
        ts = TenantService(db_session)
        ts.create("tenant-pool-a", "A")
        ts.set_payout_quota("tenant-pool-a", 3000)
        ps = TenantPoolService(db_session)
        ps.create("pool-pa", total_limit=10000)
        ps.add_member("pool-pa", "tenant-pool-a", share_ratio=1.0)
        cid = self._paid_contract(db_session, "req-pa", "tenant-pool-a", price=5000.0)
        PayoutService(db_session).generate_for_contract(cid)
        assert ps.get("pool-pa").used == 5000.0
        assert ts.get_payout_usage("tenant-pool-a")["used"] == 5000.0

    def test_payout_rejected_when_own_and_pool_over(self, db_session):
        ts = TenantService(db_session)
        ts.create("tenant-pool-b", "B")
        ts.set_payout_quota("tenant-pool-b", 3000)
        ps = TenantPoolService(db_session)
        ps.create("pool-pb", total_limit=5000)
        ps.add_member("pool-pb", "tenant-pool-b", share_ratio=0.2)  # 仅可借 1000
        cid = self._paid_contract(db_session, "req-pb", "tenant-pool-b", price=5000.0)
        with pytest.raises(PayoutLimitExceededError, match="exceeded"):
            PayoutService(db_session).generate_for_contract(cid)

    def test_payout_within_own_quota_not_touching_pool(self, db_session):
        ts = TenantService(db_session)
        ts.create("tenant-pool-c", "C")
        ts.set_payout_quota("tenant-pool-c", 10000)
        ps = TenantPoolService(db_session)
        ps.create("pool-pc", total_limit=10000)
        ps.add_member("pool-pc", "tenant-pool-c", share_ratio=1.0)
        cid = self._paid_contract(db_session, "req-pc", "tenant-pool-c", price=3000.0)
        PayoutService(db_session).generate_for_contract(cid)
        assert ps.get("pool-pc").used == 0.0  # 自有够，不动池


class TestPoolsApi:
    def _register(self, client, identity_id):
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
        from skillos.security.message_signer import MessageSigner

        return MessageSigner(signer_id=identity_id, private_key=key)

    def _post(self, client, signer, path, payload):
        return client.post(path, json=payload, headers=signer.sign_headers(payload))

    def _put(self, client, signer, path, payload):
        return client.put(path, json=payload, headers=signer.sign_headers(payload))

    def test_create_and_list_pool(self, client):
        s = self._register(client, "req-pool-1")
        r = self._post(client, s, "/pools", {"pool_id": "pool-api-1", "name": "池A", "total_limit": 50000})
        assert r.status_code == 200, r.text
        assert r.json()["pool"]["total_limit"] == 50000
        r2 = client.get("/pools")
        assert r2.status_code == 200
        assert any(p["pool_id"] == "pool-api-1" for p in r2.json()["pools"])

    def test_create_requires_signature(self, client):
        r = client.post("/pools", json={"pool_id": "pool-anon", "total_limit": 100})
        assert r.status_code == 401

    def test_add_member(self, client):
        s = self._register(client, "req-pool-2")
        self._post(client, s, "/pools", {"pool_id": "pool-api-2", "total_limit": 10000})
        r = self._post(client, s, "/pools/pool-api-2/members", {"tenant_id": "tenant-pool-api", "share_ratio": 0.5})
        assert r.status_code == 200, r.text
        assert r.json()["share_ratio"] == 0.5

    def test_set_limit_and_approve(self, client):
        s = self._register(client, "req-pool-3")
        self._post(client, s, "/pools", {"pool_id": "pool-api-3", "total_limit": 5000})
        r1 = self._put(client, s, "/pools/pool-api-3/limit", {"new_limit": 9000})
        assert r1.status_code == 200
        adj_id = r1.json()["adjustment_id"]
        r2 = self._post(client, s, f"/pools/pool-api-3/adjustments/{adj_id}/approve", {})
        assert r2.status_code == 200
        assert r2.json()["status"] == "approved"
        pool = client.get("/pools/pool-api-3").json()["pool"]
        assert pool["total_limit"] == 9000

    def test_set_limit_missing_pool_404(self, client):
        s = self._register(client, "req-pool-4")
        r = self._put(client, s, "/pools/pool-missing/limit", {"new_limit": 9000})
        assert r.status_code == 404
