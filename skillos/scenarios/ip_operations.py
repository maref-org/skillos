"""内容 IP 代运营垂直场景 — 场景化需求模板与内测数据包

定位：
  - 垂直场景（内容 IP 代运营）产品化：把「企业主意图」转化为结构化的契约需求
  - 供内测 CLI（scripts/ip_operations_trial.py）与外部 Agent 接入演示复用

设计意图：
  - 场景化需求模板 → OutcomeContractService 的 rule-based 拆解直接消费
  - 收敛内测参数（预算/工期档位/角色集），降低接入门槛
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 垂直场景默认需求（内容 IP 代运营）
DEFAULT_REQUIREMENT = "给公司公众号做 30 天内容运营，写文章并分发到多平台，最后要复盘"

# 场景角色集：契约方 + 团队预设
SCENE_ROLES: dict[str, dict[str, Any]] = {
    "business": {"role": "consumer", "desc": "企业主（需求方）"},
    "agent": {"role": "provider", "desc": "外部 Agent 构建者（项目长）"},
    "author": {"desc": "技能作者（内容创作）", "share_ratio": 0.4},
}

# 内测契约预设：主题 → 需求文本
TEMPLATES: dict[str, str] = {
    "内容代运营": DEFAULT_REQUIREMENT,
    "短视频矩阵": "给品牌做 30 天短视频内容矩阵，含脚本与成片并分发",
    "知识付费专栏": "做一套 12 节知识付费专栏课程，含大纲、逐字稿与上线物料",
}


@dataclass
class IpTrialScenario:
    """内测场景数据包。"""

    name: str
    requirement: str
    tier: str = "balanced"
    tip_ratio: float = 0.15
    team_members: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        name: str = "内容代运营",
        tier: str = "balanced",
        tip_ratio: float = 0.15,
        team: list[dict[str, Any]] | None = None,
        tenant_id: str | None = None,
        db_session: Any | None = None,
    ) -> "IpTrialScenario":
        """按模板名构建内测场景数据包。

        传入 tenant_id 时，从 TenantService.get_scene_config 读取模板/档位/小费/角色集
        覆盖默认值；租户未配置或未知时用默认模板。显式参数（name/tier/tip_ratio/team）
        优先于租户配置。
        """
        scene_config: dict[str, Any] = {}
        if tenant_id is not None:
            if db_session is not None:
                from skillos.market.tenants import TenantService

                scene_config = TenantService(db_session).get_scene_config(tenant_id) or {}
            else:
                from skillos.db.engine import get_sessionmaker

                session = get_sessionmaker()()
                try:
                    from skillos.market.tenants import TenantService

                    scene_config = TenantService(session).get_scene_config(tenant_id) or {}
                finally:
                    session.close()

        if name == "内容代运营" and scene_config.get("template"):
            name = scene_config["template"]
        if name not in TEMPLATES:
            raise ValueError(f"Unknown scenario template: {name}, choose from {list(TEMPLATES)}")

        tier = tier if tier != "balanced" else scene_config.get("tier", tier)
        tip_ratio = tip_ratio if tip_ratio != 0.15 else scene_config.get("tip_ratio", tip_ratio)
        if team is not None:
            team_members = team
        elif scene_config.get("team"):
            team_members = scene_config["team"]
        else:
            team_members = [{"member_id": "author-scene", "role": "skill_author", "share_ratio": 0.4}]

        return cls(
            name=name,
            requirement=TEMPLATES[name],
            tier=tier,
            tip_ratio=tip_ratio,
            team_members=team_members,
        )
