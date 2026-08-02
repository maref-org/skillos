"""Tests for M13-P1 — 池额度自动回收 + 调度器接线

覆盖：reclaim 归还超自有部分、未超自有不动、clamp、调度器 handler 接线。
"""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.kernel.task_scheduler import TaskScheduler
from skillos.market.outcome_contracts import OutcomeContractService, Tier
from skillos.market.payouts import PayoutService
from skillos.market.pool_reclaim import PoolReclaimService
from skillos.market.tenant_pools import TenantPoolService
from skillos.market.tenants import TenantService
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.scheduler import router as scheduler_router


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(onboarding_router)
    app.include_router(scheduler_router)
    return TestClient(app)


def _paid_contract(db_session, requester, tenant_id, price=5000.0):
    svc = OutcomeContractService(db_session)
    ctr = svc.create(requester, "做内容全流程", base_price=price)
    ctr = svc.select_tier(ctr.id, Tier.BALANCED)
    svc.create_service_team(
        ctr.id, "ctr-reclaim", [{"member_id": "author-reclaim", "role": "skill_author", "share_ratio": 0.4}]
    )
    ctr = svc.sign(ctr.id, "ctr-reclaim")
    ctr = svc.submit_delivery(ctr.id)
    ctr = svc.confirm_delivery(ctr.id, accepted=True)
    svc.settle(ctr.id)
    from skillos.db.models import OutcomeContractModel

    model = db_session.query(OutcomeContractModel).filter(OutcomeContractModel.id == ctr.id).first()
    model.tenant_id = tenant_id
    db_session.flush()
    return ctr.id


class TestPoolReclaim:
    def _setup_borrowed(self, db_session, tenant_id, own_limit, pool_limit, price):
        """租户自有超限后从池借用：池 used = price。"""
        ts = TenantService(db_session)
        ts.create(tenant_id, tenant_id)
        ts.set_payout_quota(tenant_id, own_limit)
        ps = TenantPoolService(db_session)
        ps.create("pool-reclaim", total_limit=pool_limit)
        ps.add_member("pool-reclaim", tenant_id, share_ratio=1.0)
        cid = _paid_contract(db_session, f"req-{tenant_id}", tenant_id, price=price)
        PayoutService(db_session).generate_for_contract(cid)
        assert ps.get("pool-reclaim").used == price
        return cid

    def test_reclaim_releases_when_own_no_longer_over(self, db_session):
        self._setup_borrowed(db_session, "tenant-r1", own_limit=3000, pool_limit=10000, price=5000)
        # 租户自有用量被外部调低（模拟结算/退款回退）
        TenantService(db_session).set_payout_quota("tenant-r1", 10000)
        result = PoolReclaimService(db_session).reclaim()
        assert result["total_released"] == 5000.0
        assert TenantPoolService(db_session).get("pool-reclaim").used == 0.0

    def test_reclaim_noop_when_still_over(self, db_session):
        self._setup_borrowed(db_session, "tenant-r2", own_limit=3000, pool_limit=10000, price=5000)
        result = PoolReclaimService(db_session).reclaim()
        assert result["total_released"] == 0.0
        assert TenantPoolService(db_session).get("pool-reclaim").used == 5000.0

    def test_reclaim_partial_by_surplus(self, db_session):
        self._setup_borrowed(db_session, "tenant-r3", own_limit=3000, pool_limit=10000, price=5000)
        # 自有升到 6000：富余 1000，但池 used=5000，只归还 1000
        TenantService(db_session).set_payout_quota("tenant-r3", 6000)
        result = PoolReclaimService(db_session).reclaim()
        assert result["total_released"] == 1000.0
        assert TenantPoolService(db_session).get("pool-reclaim").used == 4000.0

    def test_reclaim_respects_share_ratio(self, db_session):
        self._setup_borrowed(db_session, "tenant-r4", own_limit=3000, pool_limit=10000, price=5000)
        ps = TenantPoolService(db_session)
        # share_ratio 降到 0.5：归还量上限 = 池 used × 0.5
        member = ps.members("pool-reclaim")[0]
        member.share_ratio = 0.5
        db_session.flush()
        TenantService(db_session).set_payout_quota("tenant-r4", 10000)
        result = PoolReclaimService(db_session).reclaim()
        assert result["total_released"] == 2500.0

    def test_reclaim_scheduled_entry(self):
        import asyncio

        async def run():
            scheduler = TaskScheduler()
            return await scheduler._invoke_handler("skillos.market.pool_reclaim:reclaim_scheduled", {})

        out = asyncio.run(run())
        assert out["status"] in ("executed", "error")


class TestSchedulerHandler:
    def test_handler_dot_path(self):
        import asyncio

        async def run():
            scheduler = TaskScheduler()
            return await scheduler._invoke_handler("skillos.market.tenant_pools.TenantPoolService", {})

        out = asyncio.run(run())
        # TenantPoolService 是类，调用会实例化缺参失败 → 返回 error 状态而非抛错
        assert out["status"] == "error"

    def test_handler_missing_module(self):
        import asyncio

        async def run():
            scheduler = TaskScheduler()
            return await scheduler._invoke_handler("no.such.module:func", {})

        out = asyncio.run(run())
        assert out["status"] == "error"

    def test_handler_whitelist_blocks_rce(self):
        """I8：非 skillos. 包 handler 被白名单拦截（RCE 防护）。"""
        import asyncio

        from skillos.kernel.task_scheduler import is_allowed_handler

        # 白名单拒绝任意系统模块
        assert is_allowed_handler("os.system:exec") is False
        assert is_allowed_handler("subprocess.Popen") is False
        assert is_allowed_handler("builtins.eval") is False
        assert is_allowed_handler("os:system") is False
        # 允许 skillos 内置处理器
        assert is_allowed_handler("skillos.market.pool_reclaim:reclaim_scheduled") is True
        assert is_allowed_handler("skillos.observability.slo_alerts.evaluate") is True

        async def run_blocked():
            scheduler = TaskScheduler()
            return await scheduler._invoke_handler("os.system:exec", {"command": "id"})

        out = asyncio.run(run_blocked())
        assert out["status"] == "error"
        assert "whitelist" in out["error"]

    def test_handler_sync_function(self):
        import asyncio

        async def run():
            scheduler = TaskScheduler()
            return await scheduler._invoke_handler("skillos.market.pool_reclaim:_demo_handler", {"x": 5})

        out = asyncio.run(run())
        assert out["status"] == "executed"
        assert out["result"] == 10


class TestReclaimApi:
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

    def test_reclaim_requires_signature(self, client):
        r = client.post("/pools/reclaim", json={})
        assert r.status_code == 401

    def test_reclaim_endpoint(self, client):
        s = self._register(client, "req-reclaim-1")
        r = client.post("/pools/reclaim", json={}, headers=s.sign_headers({}))
        assert r.status_code == 200, r.text
        assert "total_released" in r.json()

    def _post(self, client, signer, path, payload):
        return client.post(path, json=payload, headers=signer.sign_headers(payload))

    def test_add_scheduler_task_invalid_handler(self, client):
        s = self._register(client, "req-sched-1")
        r = self._post(
            client, s, "/scheduler/tasks",
            {
                "task_id": "bad-task",
                "name": "x",
                "cron_expression": "0 3 * * *",
                "handler": "no.such:fn",
            },
        )
        assert r.status_code == 400

    def test_add_scheduler_task_invalid_cron(self, client):
        s = self._register(client, "req-sched-2")
        handler = "skillos.market.pool_reclaim:reclaim_scheduled"
        r = self._post(
            client, s, "/scheduler/tasks",
            {"task_id": "bad-cron", "name": "x", "cron_expression": "not-a-cron", "handler": handler},
        )
        assert r.status_code == 400

    def test_add_scheduler_task_ok(self, client):
        s = self._register(client, "req-sched-3")
        handler = "skillos.market.pool_reclaim:reclaim_scheduled"
        r = self._post(
            client, s, "/scheduler/tasks",
            {"task_id": "pool-reclaim-daily", "name": "每日回收", "cron_expression": "0 3 * * *", "handler": handler},
        )
        assert r.status_code == 200, r.text
        assert r.json()["task_id"] == "pool-reclaim-daily"

    def test_scheduler_task_requires_signature(self, client):
        handler = "skillos.market.pool_reclaim:reclaim_scheduled"
        r = client.post(
            "/scheduler/tasks",
            json={"task_id": "anon-task", "name": "x", "cron_expression": "0 3 * * *", "handler": handler},
        )
        assert r.status_code == 401
