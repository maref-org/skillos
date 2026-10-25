"""Tests for M5 — 出款指令导出（持牌支付桥接层）"""

import pytest

from skillos.market.outcome_contracts import OutcomeContractService, OutcomeContractStatus, Tier
from skillos.market.payouts import PayoutService


def _paid_contract(db_session, price=5000.0):
    """造一个已结算契约（含团队），返回 (contract_id, contractor_id)。"""
    svc = OutcomeContractService(db_session)
    ctr = svc.create("requester-pay", "做内容全流程", base_price=price)
    ctr = svc.select_tier(ctr.id, Tier.BALANCED)
    svc.create_service_team(
        ctr.id, "contractor-pay", [{"member_id": "author-pay", "role": "skill_author", "share_ratio": 0.4}]
    )
    ctr = svc.sign(ctr.id, "contractor-pay")
    ctr = svc.submit_delivery(ctr.id)
    ctr = svc.confirm_delivery(ctr.id, accepted=True)
    svc.settle(ctr.id)
    assert svc.get(ctr.id).status == OutcomeContractStatus.PAID
    return ctr.id, "contractor-pay"


class TestGeneratePayout:
    def test_generates_instructions_for_paid_contract(self, db_session):
        cid, contractor = _paid_contract(db_session)
        payouts = PayoutService(db_session)
        instructions = payouts.generate_for_contract(cid)
        assert len(instructions) >= 2
        by_role = {i.role: i for i in instructions}
        # C3 修复：贡献池 70% 在项目长与作者间划拨，项目长 = price*0.7*(1-Σshare)
        assert by_role["contractor"].amount == pytest.approx(5000.0 * 0.7 * (1 - 0.4))
        assert by_role["platform"].amount == pytest.approx(250.0)
        # 技能作者分成 = price*0.7*share_ratio（贡献池内划拨，不额外超发）
        author = [i for i in instructions if i.role == "skill_author"]
        assert author[0].amount == pytest.approx(5000.0 * 0.7 * 0.4)
        # 总额 ≤ 契约价（防超发）
        assert sum(i.amount for i in instructions) <= 5000.0

    def test_payout_total_never_exceeds_price(self, db_session):
        """C3：即使 share_ratio 合计接近 1.0，出款总额也不超契约价。"""
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-pay", "做内容全流程", base_price=5000.0)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        svc.create_service_team(
            ctr.id,
            "contractor-pay",
            [
                {"member_id": "author-a", "role": "skill_author", "share_ratio": 0.5},
                {"member_id": "author-b", "role": "skill_author", "share_ratio": 0.5},
            ],
        )
        ctr = svc.sign(ctr.id, "contractor-pay")
        ctr = svc.submit_delivery(ctr.id)
        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        svc.settle(ctr.id)
        payouts = PayoutService(db_session)
        instructions = payouts.generate_for_contract(ctr.id)
        assert sum(i.amount for i in instructions) <= 5000.0
        # 项目长应得贡献池剩余（share 合计 1.0 → 项目长 0）
        by_role = {i.role: i for i in instructions}
        assert by_role["contractor"].amount == pytest.approx(0.0)

        def test_idempotent_generation(self, db_session):
            cid, _ = _paid_contract(db_session)
            payouts = PayoutService(db_session)

            first = payouts.generate_for_contract(cid)
            second = payouts.generate_for_contract(cid)
            assert len(first) == len(second)
            assert [i.id for i in first] == [i.id for i in second]

    def test_rejects_unpaid_contract(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-pay", "做内容")
        payouts = PayoutService(db_session)
        with pytest.raises(ValueError, match="Only paid contracts"):
            payouts.generate_for_contract(ctr.id)

    def test_rejects_missing_contract(self, db_session):
        payouts = PayoutService(db_session)
        with pytest.raises(ValueError, match="Contract not found"):
            payouts.generate_for_contract("ctr-missing")


class TestExportManifest:
    def test_manifest_shape(self, db_session):
        cid, _ = _paid_contract(db_session)
        payouts = PayoutService(db_session)
        manifest = payouts.export_manifest(cid)
        assert manifest["contract_id"] == cid
        assert manifest["manifest_id"].startswith("pay-")
        assert manifest["total_amount"] > 0
        assert manifest["instructions"][0]["payee_id"]
        assert "不托管资金" in manifest["note"]

    def test_export_is_idempotent(self, db_session):
        cid, _ = _paid_contract(db_session)
        payouts = PayoutService(db_session)
        m1 = payouts.export_manifest(cid)
        m2 = payouts.export_manifest(cid)
        assert m1["total_amount"] == m2["total_amount"]
        assert len(m1["instructions"]) == len(m2["instructions"])

    def test_period_manifest(self, db_session):
        cid, _ = _paid_contract(db_session)
        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        manifest = payouts.export_period_manifest("2000-01-01", "2999-12-31")
        assert manifest["total_amount"] > 0
        assert all(i["contract_id"] == cid for i in manifest["instructions"])


class TestShareRatioGuard:
    def _contract(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-pay", "做内容全流程", base_price=5000.0)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        return svc, ctr

    def test_share_ratio_exceeding_1_rejected(self, db_session):
        """C3：share_ratio 合计 > 1.0 会被组队阶段拒绝（防负 contractor 金额绕过防超发）。"""
        svc, ctr = self._contract(db_session)
        with pytest.raises(ValueError, match="sum of share_ratio"):
            svc.create_service_team(
                ctr.id,
                "contractor-pay",
                [
                    {"member_id": "author-a", "role": "skill_author", "share_ratio": 0.6},
                    {"member_id": "author-b", "role": "skill_author", "share_ratio": 0.6},
                ],
            )

    def test_negative_share_ratio_rejected(self, db_session):
        svc, ctr = self._contract(db_session)
        with pytest.raises(ValueError, match="share_ratio must be within"):
            svc.create_service_team(
                ctr.id,
                "contractor-pay",
                [{"member_id": "author-a", "role": "skill_author", "share_ratio": -0.2}],
            )

    def test_sum_share_ratio_over_1_rejected(self, db_session):
        svc, ctr = self._contract(db_session)
        with pytest.raises(ValueError, match="sum of share_ratio"):
            svc.create_service_team(
                ctr.id,
                "contractor-pay",
                [
                    {"member_id": "author-a", "role": "skill_author", "share_ratio": 0.7},
                    {"member_id": "author-b", "role": "skill_author", "share_ratio": 0.4},
                ],
            )


class TestMarkExecuted:
    def test_mark_executed(self, db_session):
        cid, _ = _paid_contract(db_session)
        payouts = PayoutService(db_session)
        instructions = payouts.generate_for_contract(cid)
        updated = payouts.mark_executed(instructions[0].id, external_ref="bank-txn-123")
        assert updated.status == "executed"
        assert updated.external_ref == "bank-txn-123"

    def test_mark_missing(self, db_session):
        payouts = PayoutService(db_session)
        with pytest.raises(ValueError, match="not found"):
            payouts.mark_executed("pay-missing")

    def test_list_by_payee(self, db_session):
        cid, contractor = _paid_contract(db_session)
        payouts = PayoutService(db_session)
        payouts.generate_for_contract(cid)
        rows = payouts.list_by_payee(contractor)
        assert len(rows) == 1
        assert rows[0].role == "contractor"


class TestTipPayout:
    def test_tip_creates_separate_instructions(self, db_session):
        """小费应生成独立出款指令（source=tip），不再只记账不出款。"""
        cid, contractor = _paid_contract(db_session)
        svc = OutcomeContractService(db_session)
        tip = svc.add_tip(cid, "requester-pay", 0.10)

        instructions = PayoutService(db_session).generate_for_contract(cid)
        tip_instructions = [i for i in instructions if i.source == "tip"]
        assert len(tip_instructions) == 2
        assert sum(i.amount for i in tip_instructions) == pytest.approx(tip.amount)
        assert {i.payee_id for i in tip_instructions} == {contractor, "author-pay"}

    def test_tip_does_not_break_contract_total_guard(self, db_session):
        cid, _ = _paid_contract(db_session)
        svc = OutcomeContractService(db_session)
        svc.add_tip(cid, "requester-pay", 0.20)

        instructions = PayoutService(db_session).generate_for_contract(cid)
        settlement = sum(i.amount for i in instructions if i.source != "tip")
        assert settlement <= 5000.0
        assert sum(i.amount for i in instructions) > settlement


class TestManifestReconciliation:
    def test_manifest_reports_ecosystem_pending_allocation(self, db_session):
        cid, _ = _paid_contract(db_session)
        manifest = PayoutService(db_session).export_manifest(cid)
        rec = manifest["reconciliation"]
        assert rec["contract_price"] == pytest.approx(5000.0)
        assert rec["settlement_executable"] == pytest.approx(5000.0 * 0.75)
        assert rec["ecosystem_fee_recorded"] == pytest.approx(5000.0 * 0.25)
        assert rec["ecosystem_pending_allocation"] == pytest.approx(5000.0 * 0.25)
        assert "治理条款" in rec["note"]

    def test_reconciliation_tip_after_tip(self, db_session):
        cid, _ = _paid_contract(db_session)
        tip = OutcomeContractService(db_session).add_tip(cid, "requester-pay", 0.10)
        rec = PayoutService(db_session).export_manifest(cid)["reconciliation"]
        assert rec["tip_executable"] == pytest.approx(tip.amount)
