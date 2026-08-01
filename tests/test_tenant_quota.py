"""Tests for M9-P1 — 租户配额/计费隔离

覆盖：
  - TenantService.set_payout_quota / add_payout_used / get_payout_usage
  - PayoutService.generate_for_contract 租户出款限额校验（超限拒绝）
  - 幂等导出不叠加用量
"""

import pytest

from skillos.db.models import OutcomeContractModel, TenantModel
from skillos.market.outcome_contracts import OutcomeContractService, OutcomeContractStatus, Tier
from skillos.market.payouts import PayoutLimitExceededError, PayoutService
from skillos.market.tenants import TenantService


@pytest.fixture
def tenant(db_session) -> str:
    ts = TenantService(db_session)
    ts.create("t-quota", name="Quota tenant")
    return "t-quota"


def _paid_contract(db_session, requester="req-quota", price=5000.0, tenant_id=None):
    svc = OutcomeContractService(db_session)
    ctr = svc.create(requester, "做内容全流程", base_price=price)
    ctr = svc.select_tier(ctr.id, Tier.BALANCED)
    svc.create_service_team(
        ctr.id, "contractor-quota", [{"member_id": "author-quota", "role": "skill_author", "share_ratio": 0.4}]
    )
    ctr = svc.sign(ctr.id, "contractor-quota")
    ctr = svc.submit_delivery(ctr.id)
    ctr = svc.confirm_delivery(ctr.id, accepted=True)
    svc.settle(ctr.id)
    assert svc.get(ctr.id).status == OutcomeContractStatus.PAID
    if tenant_id:
        model = db_session.query(OutcomeContractModel).filter(OutcomeContractModel.id == ctr.id).first()
        model.tenant_id = tenant_id
        db_session.flush()
    return ctr.id


class TestPayoutQuotaService:
    def test_set_quota_and_usage(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-q1", name="A")
        ts.set_payout_quota("t-q1", 10000)
        usage = ts.get_payout_usage("t-q1")
        assert usage == {"limit": 10000.0, "used": 0.0, "remaining": 10000.0}

    def test_rejects_negative_quota(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-q2", name="B")
        with pytest.raises(ValueError, match="negative"):
            ts.set_payout_quota("t-q2", -1)

    def test_default_quota_is_unlimited(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-q3", name="C")
        usage = ts.get_payout_usage("t-q3")
        assert usage["limit"] == 0.0
        assert usage["remaining"] is None

    def test_add_payout_used_accumulates(self, db_session, tenant):
        ts = TenantService(db_session)
        ts.set_payout_quota(tenant, 5000)
        ts.add_payout_used(tenant, 1200)
        ts.add_payout_used(tenant, 800)
        usage = ts.get_payout_usage(tenant)
        assert usage["used"] == 2000.0
        assert usage["remaining"] == 3000.0

    def test_usage_clamps_remaining_at_zero(self, db_session, tenant):
        ts = TenantService(db_session)
        ts.set_payout_quota(tenant, 1000)
        ts.add_payout_used(tenant, 2500)
        usage = ts.get_payout_usage(tenant)
        assert usage["remaining"] == 0.0


class TestPayoutLimitEnforcement:
    def test_payout_within_quota_succeeds_and_counts(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-qok", name="OK")
        ts.set_payout_quota("t-qok", 10000)
        cid = _paid_contract(db_session, tenant_id="t-qok", price=5000.0)
        PayoutService(db_session).generate_for_contract(cid)
        assert ts.get_payout_usage("t-qok")["used"] == 5000.0

    def test_payout_over_quota_rejected(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-qno", name="NO")
        ts.set_payout_quota("t-qno", 3000)
        cid = _paid_contract(db_session, tenant_id="t-qno", price=5000.0)
        with pytest.raises(PayoutLimitExceededError, match="exceeded"):
            PayoutService(db_session).generate_for_contract(cid)

    def test_idempotent_export_no_double_count(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-qidem", name="IDEM")
        ts.set_payout_quota("t-qidem", 10000)
        cid = _paid_contract(db_session, tenant_id="t-qidem", price=4000.0)
        svc = PayoutService(db_session)
        svc.generate_for_contract(cid)
        svc.generate_for_contract(cid)
        assert ts.get_payout_usage("t-qidem")["used"] == 4000.0

    def test_payout_after_reaching_limit_rejected(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-qfull", name="FULL")
        ts.set_payout_quota("t-qfull", 6000)
        cid1 = _paid_contract(db_session, requester="req-full-1", tenant_id="t-qfull", price=4000.0)
        PayoutService(db_session).generate_for_contract(cid1)
        cid2 = _paid_contract(db_session, requester="req-full-2", tenant_id="t-qfull", price=3000.0)
        with pytest.raises(PayoutLimitExceededError, match="exceeded"):
            PayoutService(db_session).generate_for_contract(cid2)


class TestTenantQuotaPersistence:
    def test_tenant_model_has_quota_fields(self, db_session):
        ts = TenantService(db_session)
        ts.create("t-qp", name="Persist")
        ts.set_payout_quota("t-qp", 9999.0)
        row = db_session.query(TenantModel).filter(TenantModel.tenant_id == "t-qp").first()
        assert row.payout_limit == 9999.0
        assert row.payout_used == 0.0
