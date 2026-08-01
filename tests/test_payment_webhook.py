"""Tests for M6-P2 — payments webhook + submit endpoints"""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.market.payments.sandbox import SANDBOX_TOKEN
from skillos.web_api.payments import router as payments_router


def _build_client():
    app = FastAPI()
    app.include_router(payments_router)
    return TestClient(app)


@pytest.fixture
def client(db_session):
    return _build_client()


def _paid_contract(db_session):
    from skillos.market.outcome_contracts import OutcomeContractService, Tier

    svc = OutcomeContractService(db_session)
    ctr = svc.create("req-w", "做内容全流程", base_price=5000.0)
    ctr = svc.select_tier(ctr.id, Tier.BALANCED)
    svc.create_service_team(
        ctr.id, "ctr-w", [{"member_id": "author-w", "role": "skill_author", "share_ratio": 0.4}]
    )
    ctr = svc.sign(ctr.id, "ctr-w")
    ctr = svc.submit_delivery(ctr.id)
    ctr = svc.confirm_delivery(ctr.id, accepted=True)
    svc.settle(ctr.id)
    db_session.commit()
    return ctr.id


class TestListProviders:
    def test_lists_all_providers(self, client):
        r = client.get("/payments/providers")
        assert r.status_code == 200
        names = {p["name"] for p in r.json()["providers"]}
        assert names == {"sandbox", "alipay", "wechat"}
        sandbox = [p for p in r.json()["providers"] if p["name"] == "sandbox"][0]
        assert sandbox["configured"] is True
        assert sandbox["active"] == "sandbox"

    def test_alipay_not_configured(self, client, monkeypatch):
        monkeypatch.delenv("SKILLOS_ALIPAY_APP_ID", raising=False)
        monkeypatch.delenv("SKILLOS_ALIPAY_PRIVATE_KEY", raising=False)
        alipay = [p for p in client.get("/payments/providers").json()["providers"] if p["name"] == "alipay"][0]
        assert alipay["configured"] is False
        assert alipay["active"] == "sandbox"


class TestWebhook:
    def test_webhook_marks_executed(self, client, db_session):
        cid = _paid_contract(db_session)
        # 先手动出款生成指令（sandbox 已 mark_executed，重新生成一个 pending 场景）
        from skillos.market.payouts import PayoutService

        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        # 清空 external_ref 模拟回执前状态
        from skillos.db.models import PayoutInstructionModel

        for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid):
            m.status = "pending"
            m.external_ref = ""
        db_session.commit()
        ids = [m.id for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid)]

        r = client.post(
            "/payments/webhooks/sandbox",
            json={"instruction_ids": ids, "external_ref": "sandbox-abc123"},
            headers={"X-Sandbox-Token": SANDBOX_TOKEN},
        )
        assert r.status_code == 200, r.text
        assert len(r.json()["updated"]) == len(ids)
        db_session.expire_all()
        rows = (
            db_session.query(PayoutInstructionModel)
            .filter(PayoutInstructionModel.contract_id == cid)
            .all()
        )
        assert all(m.status == "executed" for m in rows)
        assert all(m.external_ref == "sandbox-abc123" for m in rows)

    def test_webhook_bad_token_401(self, client):
        r = client.post(
            "/payments/webhooks/sandbox",
            json={"instruction_ids": ["pay-1"]},
            headers={"X-Sandbox-Token": "wrong"},
        )
        assert r.status_code == 401

    def test_webhook_unknown_provider_404(self, client):
        r = client.post("/payments/webhooks/stripe", json={})
        assert r.status_code == 404


class TestWebhookExternalRefMapping:
    """M7-P1.1 — 回执单号映射：支付宝 out_biz_no / 微信 out_bill_no / sandbox external_ref。"""

    def test_alipay_uses_out_biz_no(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SKILLOS_ALIPAY_APP_ID", "app-test")
        monkeypatch.setenv("SKILLOS_ALIPAY_PRIVATE_KEY", "dummy-private-key")
        cid = _paid_contract(db_session)
        from skillos.market.payouts import PayoutService

        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        from skillos.db.models import PayoutInstructionModel

        for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid):
            m.status = "pending"
            m.external_ref = ""
        db_session.commit()
        ids = [m.id for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid)]

        r = client.post(
            "/payments/webhooks/alipay",
            json={
                "app_id": "app-test",
                "notify_type": "fund_trans_order_status",
                "status": "SUCCESS",
                "instruction_ids": ids,
                "out_biz_no": "alipay-real-1",
            },
        )
        assert r.status_code == 200, r.text
        assert all(i["external_ref"] == "alipay-real-1" for i in r.json()["updated"])

    def test_wechat_uses_out_bill_no(self, client, db_session, monkeypatch):
        monkeypatch.setenv("SKILLOS_WECHAT_MCH_ID", "mch-1")
        monkeypatch.setenv("SKILLOS_WECHAT_APIV3_KEY", "v3-key")
        cid = _paid_contract(db_session)
        from skillos.market.payouts import PayoutService

        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        from skillos.db.models import PayoutInstructionModel

        for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid):
            m.status = "pending"
            m.external_ref = ""
        db_session.commit()
        ids = [m.id for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid)]

        r = client.post(
            "/payments/webhooks/wechat",
            json={
                "event_type": "TRANSFER.TRANSFER_SUCCESS",
                "resource": {"instruction_ids": ids, "out_bill_no": "wx-real-1"},
            },
            headers={"Wechatpay-Serial": "sn-1"},
        )
        assert r.status_code == 200, r.text
        assert all(i["external_ref"] == "wx-real-1" for i in r.json()["updated"])

    def test_sandbox_uses_external_ref(self, client, db_session):
        cid = _paid_contract(db_session)
        from skillos.market.payouts import PayoutService

        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        from skillos.db.models import PayoutInstructionModel

        for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid):
            m.status = "pending"
            m.external_ref = ""
        db_session.commit()
        ids = [m.id for m in db_session.query(PayoutInstructionModel).filter(PayoutInstructionModel.contract_id == cid)]

        r = client.post(
            "/payments/webhooks/sandbox",
            json={"instruction_ids": ids, "external_ref": "sbx-1"},
            headers={"X-Sandbox-Token": SANDBOX_TOKEN},
        )
        assert r.status_code == 200, r.text
        assert all(i["external_ref"] == "sbx-1" for i in r.json()["updated"])


class TestSubmitContract:
    def test_submit_paid_contract(self, client, db_session):
        cid = _paid_contract(db_session)
        r = client.post(f"/payments/contracts/{cid}/submit", json={"provider": "sandbox"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["provider"] == "sandbox"
        assert body["external_ref"].startswith("sandbox-")
        assert body["status"] == "succeeded"
        assert len(body["instructions"]) >= 3

    def test_submit_unpaid_contract_400(self, client, db_session):
        from skillos.market.outcome_contracts import OutcomeContractService

        svc = OutcomeContractService(db_session)
        ctr = svc.create("req-w", "做内容")
        r = client.post(f"/payments/contracts/{ctr.id}/submit", json={"provider": "sandbox"})
        assert r.status_code == 400

    def test_submit_missing_contract_400(self, client):
        r = client.post("/payments/contracts/ctr-nope/submit", json={"provider": "sandbox"})
        assert r.status_code == 400
