"""Tests for M6-P4 — 内容 IP 代运营垂直场景包"""

import pytest

from skillos.scenarios.ip_operations import DEFAULT_REQUIREMENT, TEMPLATES, IpTrialScenario


class TestIpTrialScenario:
    def test_default_scenario(self):
        s = IpTrialScenario.build()
        assert s.name == "内容代运营"
        assert s.requirement == DEFAULT_REQUIREMENT
        assert s.tier == "balanced"
        assert s.tip_ratio == 0.15
        assert s.team_members[0]["share_ratio"] == 0.4

    def test_all_templates_build(self):
        for name in TEMPLATES:
            s = IpTrialScenario.build(name)
            assert s.name == name
            assert s.requirement == TEMPLATES[name]

    def test_custom_tier_and_tip(self):
        s = IpTrialScenario.build(tier="sprint", tip_ratio=0.20)
        assert s.tier == "sprint"
        assert s.tip_ratio == 0.20

    def test_custom_team(self):
        team = [{"member_id": "writer-1", "role": "skill_author", "share_ratio": 0.6}]
        s = IpTrialScenario.build(team=team)
        assert s.team_members == team

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError, match="Unknown scenario template"):
            IpTrialScenario.build("不存在的模板")

    def test_build_with_tenant_override(self, db_session):
        """租户 scene_config 覆盖模板/档位/小费/角色集。"""
        from skillos.market.tenants import TenantService

        tsvc = TenantService(db_session)
        tsvc.create(
            "tenant-ops",
            "内容代运营事业部",
            scene_config={
                "template": "短视频矩阵",
                "tier": "sprint",
                "tip_ratio": 0.20,
                "team": [{"member_id": "video-author", "role": "skill_author", "share_ratio": 0.5}],
            },
        )

        s = IpTrialScenario.build(tenant_id="tenant-ops")
        assert s.name == "短视频矩阵"
        assert s.requirement == TEMPLATES["短视频矩阵"]
        assert s.tier == "sprint"
        assert s.tip_ratio == 0.20
        assert s.team_members == [{"member_id": "video-author", "role": "skill_author", "share_ratio": 0.5}]

    def test_build_with_tenant_partial_override(self, db_session):
        """租户 scene_config 只覆盖部分字段，其余用默认。"""
        from skillos.market.tenants import TenantService

        tsvc = TenantService(db_session)
        tsvc.create("tenant-partial", "部分配置", scene_config={"template": "知识付费专栏"})

        s = IpTrialScenario.build(tenant_id="tenant-partial")
        assert s.name == "知识付费专栏"
        assert s.tier == "balanced"
        assert s.tip_ratio == 0.15

    def test_build_with_unknown_tenant_uses_default(self, db_session):
        """未知租户降级为默认模板。"""
        s = IpTrialScenario.build(tenant_id="tenant-unknown")
        assert s.name == "内容代运营"
        assert s.requirement == DEFAULT_REQUIREMENT

    def test_explicit_args_win_over_tenant_config(self, db_session):
        """显式参数优先于租户配置。"""
        from skillos.market.tenants import TenantService

        tsvc = TenantService(db_session)
        tsvc.create("tenant-explicit", "显式优先", scene_config={"tier": "stable", "tip_ratio": 0.10})

        s = IpTrialScenario.build(name="短视频矩阵", tier="sprint", tip_ratio=0.20, tenant_id="tenant-explicit")
        assert s.name == "短视频矩阵"
        assert s.tier == "sprint"
        assert s.tip_ratio == 0.20


class TestTemplatesMapToRuleDecompose:
    def test_default_requirement_decomposes(self):
        from skillos.market.outcome_contracts import rule_based_decompose

        deliverables = rule_based_decompose(DEFAULT_REQUIREMENT)
        names = [d.name for d in deliverables]
        # 内容代运营模板应拆出 内容策略/内容图文/多平台分发/复盘报告
        assert "内容图文" in names
        assert "多平台分发" in names
        assert "复盘报告" in names

    def test_short_video_template_decomposes(self):
        from skillos.market.outcome_contracts import rule_based_decompose

        deliverables = rule_based_decompose(TEMPLATES["短视频矩阵"])
        names = [d.name for d in deliverables]
        assert "视频脚本" in names
        assert "成片交付" in names
        assert "多平台分发" in names
