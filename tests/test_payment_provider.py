"""Tests for M6-P1 — PaymentProvider 抽象 + Sandbox + 双平台 adapter"""

import pytest

from skillos.market.payments.base import get_provider
from skillos.market.payments.sandbox import SANDBOX_TOKEN, SandboxProvider


class TestProviderFactory:
    def test_default_is_sandbox(self, monkeypatch):
        monkeypatch.delenv("SKILLOS_PAYMENT_PROVIDER", raising=False)
        provider = get_provider()
        assert provider.name == "sandbox"

    def test_explicit_sandbox(self):
        assert get_provider("sandbox").name == "sandbox"

    def test_alipay_without_key_downgrades_to_sandbox(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_PAYMENT_PROVIDER", "alipay")
        monkeypatch.delenv("SKILLOS_ALIPAY_APP_ID", raising=False)
        monkeypatch.delenv("SKILLOS_ALIPAY_PRIVATE_KEY", raising=False)
        provider = get_provider()
        assert provider.name == "sandbox"

    def test_wechat_without_key_downgrades_to_sandbox(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_PAYMENT_PROVIDER", "wechat")
        monkeypatch.delenv("SKILLOS_WECHAT_MCH_ID", raising=False)
        monkeypatch.delenv("SKILLOS_WECHAT_APIV3_KEY", raising=False)
        provider = get_provider()
        assert provider.name == "sandbox"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown payment provider"):
            get_provider("stripe")


class TestSandboxProvider:
    def setup_method(self):
        self.provider = SandboxProvider()

    def test_submit_returns_succeeded_ref(self):
        ref = self.provider.submit_manifest({"total_amount": 100.0, "manifest_id": "pay-x"})
        assert ref.provider == "sandbox"
        assert ref.external_ref.startswith("sandbox-")
        assert ref.status == "succeeded"

    def test_query_status(self):
        status = self.provider.query_status("sandbox-abc")
        assert status.status == "succeeded"
        assert status.external_ref == "sandbox-abc"

    def test_verify_webhook_ok(self):
        receipt = self.provider.verify_webhook(
            {"x-sandbox-token": SANDBOX_TOKEN},
            {"instruction_ids": ["pay-1", "pay-2"]},
        )
        assert receipt.instruction_ids == ["pay-1", "pay-2"]

    def test_verify_webhook_bad_token(self):
        with pytest.raises(ValueError, match="invalid sandbox webhook token"):
            self.provider.verify_webhook(
                {"x-sandbox-token": "wrong"},
                {"instruction_ids": ["pay-1"]},
            )

    def test_verify_webhook_missing_ids(self):
        with pytest.raises(ValueError, match="missing instruction_ids"):
            self.provider.verify_webhook(
                {"x-sandbox-token": SANDBOX_TOKEN},
                {},
            )


class TestSubmitContractPayout:
    def test_submits_and_marks_executed(self, db_session):
        from skillos.market.outcome_contracts import OutcomeContractService, Tier
        from skillos.market.payments import submit_contract_payout
        from skillos.market.payments.base import get_provider
        from skillos.market.payouts import PayoutService

        svc = OutcomeContractService(db_session)
        ctr = svc.create("req-pay", "做内容全流程", base_price=5000.0)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        svc.create_service_team(
            ctr.id, "ctr-pay", [{"member_id": "author-pay", "role": "skill_author", "share_ratio": 0.4}]
        )
        ctr = svc.sign(ctr.id, "ctr-pay")
        ctr = svc.submit_delivery(ctr.id)
        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        svc.settle(ctr.id)

        result = submit_contract_payout(db_session, ctr.id, provider=get_provider("sandbox"))
        assert result["provider"] == "sandbox"
        assert result["external_ref"].startswith("sandbox-")
        assert result["status"] == "succeeded"
        assert len(result["instructions"]) >= 3

        # 所有指令都被回写 executed
        payouts = PayoutService(db_session)
        for row in result["instructions"]:
            instruction = payouts.list_by_payee(row["payee_id"])[0]
            assert instruction.status == "executed"
            assert instruction.external_ref == result["external_ref"]

    def test_rejects_unpaid_contract(self, db_session):
        from skillos.market.outcome_contracts import OutcomeContractService
        from skillos.market.payments import submit_contract_payout

        svc = OutcomeContractService(db_session)
        ctr = svc.create("req-pay", "做内容")
        with pytest.raises(ValueError, match="Only paid contracts"):
            submit_contract_payout(db_session, ctr.id)
