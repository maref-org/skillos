"""Tests for M3 — 五层风控组件（L2 保证金 / L3 存证合规 / L4 仲裁）"""

import pytest

from skillos.market.outcome_contracts import OutcomeContractService, OutcomeContractStatus, Tier


def _to_disputed(svc, requester="requester-r", contractor="contractor-r"):
    ctr = svc.create(requester, "做内容全流程", base_price=5000.0)
    ctr = svc.select_tier(ctr.id, Tier.BALANCED)
    ctr = svc.sign(ctr.id, contractor)
    ctr = svc.submit_delivery(ctr.id, evidence_text="交付物内容，引用 https://example.com/doc")
    ctr = svc.confirm_delivery(ctr.id, accepted=False)
    assert ctr.status == OutcomeContractStatus.DISPUTED
    return ctr


class TestL2DepositGuarantee:
    def test_deposit_status_held_until_settle(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容全流程", base_price=5000.0)
        assert ctr.deposit_status == "held"
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        assert ctr.deposit_status == "held"
        assert ctr.deposit == pytest.approx(500.0)

    def test_deposit_released_on_settle(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容全流程", base_price=5000.0)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        ctr = svc.sign(ctr.id, "contractor-1")
        ctr = svc.submit_delivery(ctr.id)
        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        result = svc.settle(ctr.id)
        assert result["deposit_status"] == "released"
        assert svc.get(ctr.id).deposit_status == "released"

    def test_deposit_status_held_on_dispute(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        assert ctr.deposit_status == "held"

    def test_deposit_forfeited_on_reject_arbitration(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        result = svc.arbitrate(ctr.id, {"v1": "reject", "v2": "reject", "v3": "reject"})
        assert result["decision"] == "reject"
        assert result["deposit_status"] == "forfeited"
        assert svc.get(ctr.id).status == OutcomeContractStatus.CANCELLED


class TestL3EvidenceCompliance:
    def test_evidence_hash_preserved(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.select_tier(ctr.id, Tier.STABLE)
        ctr = svc.sign(ctr.id, "contractor-1")
        ctr = svc.submit_delivery(ctr.id, evidence_text="正常交付物：30 天内容日历，无引用，无异常数据")
        assert ctr.evidence_hash is not None
        assert len(ctr.evidence_hash) == 32
        assert ctr.evidence_risk is not None
        assert ctr.evidence_risk < 0.25

    def test_high_risk_evidence_rejected(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.select_tier(ctr.id, Tier.STABLE)
        ctr = svc.sign(ctr.id, "contractor-1")
        bad = "报告称成功率 150%，覆盖率 200%，转化率 300%，且引用 https://invalid 数据"
        with pytest.raises(ValueError, match="failed compliance"):
            svc.submit_delivery(ctr.id, evidence_text=bad)
        assert svc.get(ctr.id).status == OutcomeContractStatus.IN_PROGRESS

    def test_empty_evidence_allowed_without_hash(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.select_tier(ctr.id, Tier.STABLE)
        ctr = svc.sign(ctr.id, "contractor-1")
        ctr = svc.submit_delivery(ctr.id)
        assert ctr.evidence_hash is None
        assert ctr.evidence_risk is None
        assert ctr.status == OutcomeContractStatus.SUBMITTED


class TestL4Arbitration:
    def test_approve_reaches_consensus(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        result = svc.arbitrate(ctr.id, {"v1": "approve", "v2": "approve", "v3": "approve"})
        assert result["decision"] == "approve"
        assert result["required_agreements"] == 3
        assert svc.get(ctr.id).status == OutcomeContractStatus.WORK_COMPLETED
        assert svc.get(ctr.id).deposit_status == "released"

    def test_mixed_votes_no_consensus_pending(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        result = svc.arbitrate(ctr.id, {"v1": "approve", "v2": "reject", "v3": "approve"})
        assert result["decision"] == "pending"
        assert svc.get(ctr.id).status == OutcomeContractStatus.DISPUTED

    def test_reject_forfeits_deposit(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        result = svc.arbitrate(ctr.id, {"v1": "reject", "v2": "reject", "v3": "reject"})
        assert result["decision"] == "reject"
        assert svc.get(ctr.id).status == OutcomeContractStatus.CANCELLED
        assert svc.get(ctr.id).deposit_status == "forfeited"

    def test_arbitrate_only_disputed(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        with pytest.raises(ValueError, match="Only disputed"):
            svc.arbitrate(ctr.id, {"v1": "approve"})

    def test_invalid_vote_value(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        with pytest.raises(ValueError, match="Invalid vote value"):
            svc.arbitrate(ctr.id, {"v1": "maybe", "v2": "approve", "v3": "approve"})

    def test_requires_minimum_validators(self, db_session):
        """C4：单票/两票无法通关仲裁（防操纵）。"""
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        with pytest.raises(ValueError, match="at least 3 validators"):
            svc.arbitrate(ctr.id, {"v1": "approve"})
        with pytest.raises(ValueError, match="at least 3 validators"):
            svc.arbitrate(ctr.id, {"v1": "approve", "v2": "approve"})

    def test_disputing_parties_cannot_arbitrate(self, db_session):
        """C4：requester/contractor 不得参与仲裁。"""
        svc = OutcomeContractService(db_session)
        ctr = _to_disputed(svc)
        with pytest.raises(ValueError, match="Disputing parties"):
            svc.arbitrate(ctr.id, {"requester-r": "approve", "v2": "approve", "v3": "approve"})
        with pytest.raises(ValueError, match="Disputing parties"):
            svc.arbitrate(ctr.id, {"contractor-r": "approve", "v2": "approve", "v3": "approve"})


class TestFullLifecycleWithRiskControls:
    def test_end_to_end_happy_path(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-e2e", "做内容全流程并多平台分发", base_price=8000.0)
        ctr = svc.select_tier(ctr.id, Tier.SPRINT)
        assert ctr.deposit == pytest.approx(1280.0)

        team_id = svc.create_service_team(
            ctr.id, "contractor-e2e", [{"member_id": "author-1", "role": "skill_author", "share_ratio": 0.4}]
        )
        assert team_id.startswith("team-")

        ctr = svc.sign(ctr.id, "contractor-e2e")
        ctr = svc.submit_delivery(ctr.id, evidence_text="已发布成片 30 支，合规检查通过，无异常引用")
        assert ctr.evidence_hash is not None

        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        assert ctr.status == OutcomeContractStatus.WORK_COMPLETED
        assert ctr.deposit_status == "released"

        tip = svc.add_tip(ctr.id, "requester-e2e", ratio=0.20)
        assert tip.amount == pytest.approx(2560.0)
        assert tip.distributions[0]["member_id"] == "contractor-e2e"
        assert len(tip.distributions) == 2

        result = svc.settle(ctr.id)
        assert result["amount"] == 12800.0
        assert result["deposit_status"] == "released"
        assert svc.get(ctr.id).status == OutcomeContractStatus.PAID

    def test_dispute_then_arbitration_approve(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-e2e", "做内容全流程", base_price=5000.0)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        ctr = svc.sign(ctr.id, "contractor-e2e")
        ctr = svc.submit_delivery(ctr.id, evidence_text="交付成果：内容策略 + 30 天日历，合规通过")
        ctr = svc.confirm_delivery(ctr.id, accepted=False)
        result = svc.arbitrate(ctr.id, {"v1": "approve", "v2": "approve", "v3": "approve"})
        assert result["decision"] == "approve"
        ctr = svc.get(ctr.id)
        assert ctr.status == OutcomeContractStatus.WORK_COMPLETED
        settled = svc.settle(ctr.id)
        assert settled["deposit_status"] == "released"
