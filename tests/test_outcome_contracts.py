"""Tests for skillos.market.outcome_contracts — 成果契约服务

覆盖:
  - 需求规则拆解（内容 IP 垂直场景）
  - 三方案报价（价格/成功率/工期档位）
  - 契约生命周期: create → select_tier → sign → submit → confirm → settle
  - 争议分支 / 取消 / 小费分配 / 非法状态转换
"""

import pytest

from skillos.market.outcome_contracts import (
    OutcomeContractService,
    OutcomeContractStatus,
    Tier,
    rule_based_decompose,
)


class TestDecomposeRequirement:
    def test_content_full_flow(self):
        items = rule_based_decompose("我要把我产品的内容全流程做好")
        names = [d.name for d in items]
        assert "内容策略文档" in names
        assert "复盘报告" in names

    def test_video_keyword(self):
        items = rule_based_decompose("做一个短视频全流程，包括视频号分发")
        names = [d.name for d in items]
        assert "视频脚本" in names
        assert "成片交付" in names
        assert "多平台分发" in names

    def test_marketing_keyword(self):
        items = rule_based_decompose("内容营销投放，要数据复盘和增长")
        names = [d.name for d in items]
        assert "投放策略" in names
        assert "数据复盘" in names

    def test_decompose_via_service(self, db_session):
        svc = OutcomeContractService(db_session)
        items = svc.decompose_requirement("做内容")
        assert len(items) >= 2


class TestGeneratePlans:
    def test_three_tiers_pricing_order(self, db_session):
        svc = OutcomeContractService(db_session)
        plans = svc.generate_plans("做内容全流程", base_price=5000.0)
        assert len(plans) == 3
        by_tier = {p.tier: p for p in plans}
        assert by_tier[Tier.STABLE].price < by_tier[Tier.BALANCED].price < by_tier[Tier.SPRINT].price
        assert by_tier[Tier.STABLE].price == 3000.0
        assert by_tier[Tier.BALANCED].price == 5000.0
        assert by_tier[Tier.SPRINT].price == 8000.0

    def test_success_rate_desc(self, db_session):
        svc = OutcomeContractService(db_session)
        plans = {p.tier: p for p in svc.generate_plans("做内容")}
        assert plans[Tier.STABLE].success_rate > plans[Tier.BALANCED].success_rate > plans[Tier.SPRINT].success_rate

    def test_delivery_days(self, db_session):
        svc = OutcomeContractService(db_session)
        plans = {p.tier: p for p in svc.generate_plans("做内容")}
        assert plans[Tier.STABLE].delivery_days >= plans[Tier.BALANCED].delivery_days >= plans[Tier.SPRINT].delivery_days
        assert plans[Tier.BALANCED].deposit > 0


class TestOutcomeContractLifecycle:
    def test_full_flow(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容全流程", base_price=5000.0)
        assert ctr.status == OutcomeContractStatus.DRAFT
        assert len(ctr.deliverables) >= 2

        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        assert ctr.status == OutcomeContractStatus.OPEN
        assert ctr.price == 5000.0
        assert ctr.success_rate_commitment == 0.85

        ctr = svc.sign(ctr.id, "contractor-1")
        assert ctr.status == OutcomeContractStatus.IN_PROGRESS
        assert ctr.contractor_id == "contractor-1"

        ctr = svc.submit_delivery(ctr.id)
        assert ctr.status == OutcomeContractStatus.SUBMITTED

        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        assert ctr.status == OutcomeContractStatus.WORK_COMPLETED

        result = svc.settle(ctr.id)
        assert result["contract_id"] == ctr.id
        assert result["amount"] == 5000.0
        assert result["platform_fee"] == pytest.approx(250.0)
        assert result["ecosystem_fee"] == pytest.approx(1250.0)
        assert result["contributor_pool"] == pytest.approx(3500.0)
        assert svc.get(ctr.id).status == OutcomeContractStatus.PAID

    def test_disputed_branch(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.select_tier(ctr.id, Tier.STABLE)
        ctr = svc.sign(ctr.id, "contractor-1")
        ctr = svc.submit_delivery(ctr.id)
        ctr = svc.confirm_delivery(ctr.id, accepted=False)
        assert ctr.status == OutcomeContractStatus.DISPUTED

    def test_cancel_draft(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.cancel(ctr.id)
        assert ctr.status == OutcomeContractStatus.CANCELLED

    def test_invalid_tier(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        with pytest.raises(ValueError, match="Invalid tier"):
            svc.select_tier(ctr.id, "ultra")

    def test_select_tier_twice(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        svc.select_tier(ctr.id, Tier.STABLE)
        with pytest.raises(ValueError, match="Only draft contracts"):
            svc.select_tier(ctr.id, Tier.SPRINT)

    def test_sign_non_open(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        with pytest.raises(ValueError, match="Only open contracts"):
            svc.sign(ctr.id, "contractor-1")

    def test_settle_before_complete(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.select_tier(ctr.id, Tier.STABLE)
        with pytest.raises(ValueError, match="Only completed contracts"):
            svc.settle(ctr.id)


class TestTip:
    def _completed(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容", base_price=5000.0)
        ctr = svc.select_tier(ctr.id, Tier.BALANCED)
        ctr = svc.sign(ctr.id, "contractor-1")
        ctr = svc.submit_delivery(ctr.id)
        ctr = svc.confirm_delivery(ctr.id, accepted=True)
        return svc, ctr

    def test_tip_ratio_bounds(self, db_session):
        svc, ctr = self._completed(db_session)
        with pytest.raises(ValueError, match="within"):
            svc.add_tip(ctr.id, "requester-1", 0.05)
        with pytest.raises(ValueError, match="within"):
            svc.add_tip(ctr.id, "requester-1", 0.30)

    def test_tip_requester_only(self, db_session):
        svc, ctr = self._completed(db_session)
        with pytest.raises(ValueError, match="Only the requester"):
            svc.add_tip(ctr.id, "other-user", 0.15)

    def test_tip_distribution_with_team(self, db_session):
        svc, ctr = self._completed(db_session)
        svc.create_service_team(
            ctr.id,
            lead_id="contractor-1",
            members=[
                {"member_id": "skill-author-1", "role": "skill_author", "share_ratio": 0.5},
                {"member_id": "skill-author-2", "role": "skill_author", "share_ratio": 0.5},
            ],
        )
        tip = svc.add_tip(ctr.id, "requester-1", 0.20)
        assert tip.amount == 1000.0
        lead = next(d for d in tip.distributions if d["role"] == "lead")
        assert lead["amount"] == 500.0
        authors = [d for d in tip.distributions if d["role"] == "skill_author"]
        assert len(authors) == 2
        assert all(a["amount"] == 250.0 for a in authors)

    def test_tip_without_team_goes_to_lead(self, db_session):
        svc, ctr = self._completed(db_session)
        tip = svc.add_tip(ctr.id, "requester-1", 0.10)
        assert tip.amount == 500.0
        assert tip.distributions[0]["role"] == "lead"
        assert tip.distributions[0]["amount"] == 500.0

    def test_tip_before_completed_rejected(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        ctr = svc.select_tier(ctr.id, Tier.STABLE)
        with pytest.raises(ValueError, match="only allowed after work completed"):
            svc.add_tip(ctr.id, "requester-1", 0.15)


class TestServiceTeam:
    def test_create_team(self, db_session):
        svc = OutcomeContractService(db_session)
        ctr = svc.create("requester-1", "做内容")
        team_id = svc.create_service_team(
            ctr.id,
            lead_id="lead-1",
            members=[{"member_id": "author-1", "role": "skill_author", "share_ratio": 1.0}],
        )
        assert team_id.startswith("team-")
