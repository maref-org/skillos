"""Outcome Contract Service — 成果契约服务（L3 市场层）

把业务需求翻译为可验收、可定价的成果单元，按三方案（A/B/C 档）报价，
选档签约后由服务团队执行，按成果验收与结算（含超预期小费）。

状态机: draft → open → in_progress → submitted → work_completed → paid
另有 disputed（争议）/ cancelled。

定位为协议内核记账层：结算复用 DistributionEngine（5/25/70），
不托管真实资金（红线 §9），deposit 为履约保证金记账字段，法币支付由下游持牌平台承接。
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.audit import AuditEventType, log_audit
from skillos.collaboration.reputation import TrustReputationEngine
from skillos.db.models import (
    OutcomeContractModel,
    ServiceTeamMemberModel,
    ServiceTeamModel,
    TipModel,
)
from skillos.distribution.engine import DistributionEngine
from skillos.types import SkillCall

logger = logging.getLogger(__name__)

_SLO_NAME = "negmarket_api"


def _record_settle_metric(success: bool) -> None:
    """SLO 埋点（M9-P2）：结算作为 negmarket_api 可用性观测点。

    避免循环依赖：kernel.slo 的 get_slo_manager 在调用时才加载。
    """
    from skillos.kernel.slo import get_slo_manager

    slo = get_slo_manager()
    slo.record_availability(_SLO_NAME, success)


class OutcomeContractStatus:
    DRAFT = "draft"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    WORK_COMPLETED = "work_completed"
    PAID = "paid"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"


class Tier:
    STABLE = "stable"
    BALANCED = "balanced"
    SPRINT = "sprint"


DEPOSIT_RATIO = 0.10
TIP_MIN_RATIO = 0.10
TIP_MAX_RATIO = 0.20
TIP_LEAD_SHARE_RATIO = 0.50
BASE_PRICE_PER_DELIVERABLE = 500.0
BASE_DAYS_PER_DELIVERABLE = 2.0

# C4 修复：L4 仲裁最少独立验证者票数（防止单票操纵裁决）
MIN_ARBITRATION_VOTES = 3

# 三方案档位配置：成功率承诺 × 价格系数 × 工期系数
TIER_CONFIG: dict[str, dict[str, Any]] = {
    Tier.STABLE: {
        "label": "稳妥版",
        "description": "使用高成功率技能组合，保守交付，价格低、工期长",
        "success_rate": 0.95,
        "price_factor": 0.6,
        "days_factor": 1.4,
    },
    Tier.BALANCED: {
        "label": "均衡版",
        "description": "平衡成本与产出，覆盖面更广",
        "success_rate": 0.85,
        "price_factor": 1.0,
        "days_factor": 1.0,
    },
    Tier.SPRINT: {
        "label": "冲刺版",
        "description": "最高目标产出，可能超预期，价格高、工期短",
        "success_rate": 0.70,
        "price_factor": 1.6,
        "days_factor": 0.7,
    },
}


@dataclass
class Deliverable:
    name: str
    acceptance_criteria: str = ""
    status: str = "pending"


@dataclass
class QuotePlan:
    tier: str
    label: str
    description: str
    success_rate: float
    price: float
    delivery_days: int
    deposit: float


@dataclass
class OutcomeContract:
    id: str
    requester_id: str
    contractor_id: str
    tenant_id: str | None
    tier: str
    requirement_text: str
    deliverables: list[Deliverable]
    base_price: float
    price: float
    currency: str
    deposit: float
    deposit_status: str
    evidence_hash: str | None
    evidence_risk: float | None
    success_rate_commitment: float
    status: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, model: OutcomeContractModel) -> "OutcomeContract":
        return cls(
            id=model.id,
            requester_id=model.requester_id,
            contractor_id=model.contractor_id,
            tenant_id=model.tenant_id,
            tier=model.tier,
            requirement_text=model.requirement_text,
            deliverables=[Deliverable(**d) for d in (model.deliverables or [])],
            base_price=model.base_price,
            price=model.price,
            currency=model.currency,
            deposit=model.deposit,
            deposit_status=model.deposit_status,
            evidence_hash=model.evidence_hash,
            evidence_risk=model.evidence_risk,
            success_rate_commitment=model.success_rate_commitment,
            status=model.status,
            deadline=model.deadline,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


@dataclass
class Tip:
    id: str
    contract_id: str
    requester_id: str
    amount: float
    ratio: float
    distributions: list[dict[str, Any]]
    created_at: datetime

    @classmethod
    def from_orm(cls, model: TipModel) -> "Tip":
        return cls(
            id=model.id,
            contract_id=model.contract_id,
            requester_id=model.requester_id,
            amount=model.amount,
            ratio=model.ratio,
            distributions=model.distributions or [],
            created_at=model.created_at,
        )


class LLMClient:
    """需求拆解 LLM 抽象接口 — 首个 LLM 调用点。

    实现方提供 `decompose_requirement(text) -> list[dict]`（key: name/acceptance_criteria）。
    不可用或抛错时由 OutcomeContractService 自动降级到规则拆解。
    """

    def decompose_requirement(self, requirement_text: str) -> list[dict[str, Any]]:
        raise NotImplementedError


def rule_based_decompose(requirement_text: str) -> list[Deliverable]:
    """内容 IP 生产垂直场景的规则拆解（LLM 降级路径）。"""
    text = requirement_text.lower()
    base = [
        Deliverable("内容策略文档", "明确目标人群、内容方向与选题框架"),
    ]

    if any(k in text for k in ("视频", "短视频", "视频号", "b站", "抖音")):
        base.extend(
            [
                Deliverable("视频脚本", "分镜脚本与口播文案，合规检查通过"),
                Deliverable("成片交付", "按时长要求输出，画面与字幕无差错"),
            ]
        )
    if any(k in text for k in ("文章", "文案", "图文", "公众号", "小红书", "博客", "内容")):
        base.append(Deliverable("内容图文", "图文内容，通过合规与原创性检查"))
    if any(k in text for k in ("分发", "多平台", "矩阵", "发布")):
        base.append(Deliverable("多平台分发", "跨平台发布成功，冲突率为 0"))
    if any(k in text for k in ("日历", "排期", "规划")):
        base.append(Deliverable("内容日历", "30 天排期，冲突检测通过"))
    if any(k in text for k in ("投放", "营销", "增长", "转化")):
        base.append(Deliverable("投放策略", "渠道选择与预算分配方案"))
        base.append(Deliverable("数据复盘", "投放数据报告与优化建议"))

    base.append(Deliverable("复盘报告", "交付数据回顾与下周期建议"))
    return base


class OutcomeContractService:
    """成果契约服务 — 需求拆解、三方案报价、签约、验收、小费、结算。"""

    def __init__(
        self,
        db_session: Session,
        llm_client: LLMClient | None = None,
        reputation_engine: TrustReputationEngine | None = None,
    ):
        self._db = db_session
        self._llm = llm_client
        self._reputation = reputation_engine or TrustReputationEngine()
        self._dist_engine = DistributionEngine(db_session=db_session)

    # ------------------------------------------------------------------
    # 需求拆解 + 三方案报价
    # ------------------------------------------------------------------
    def decompose_requirement(self, requirement_text: str) -> list[Deliverable]:
        if self._llm is not None:
            try:
                items = self._llm.decompose_requirement(requirement_text)
                if items:
                    return [Deliverable(**i) for i in items]
            except Exception as exc:  # 降级，不阻断主流程
                logger.warning("LLM decompose failed, fallback to rule-based: %s", exc)
        return rule_based_decompose(requirement_text)

    def generate_plans(self, requirement_text: str, base_price: float | None = None) -> list[QuotePlan]:
        deliverables = self.decompose_requirement(requirement_text)
        n = len(deliverables) or 1
        base = base_price if base_price and base_price > 0 else n * BASE_PRICE_PER_DELIVERABLE
        base_days = max(3, int(n * BASE_DAYS_PER_DELIVERABLE))

        plans: list[QuotePlan] = []
        for tier, cfg in TIER_CONFIG.items():
            price = round(base * cfg["price_factor"], 2)
            days = max(1, int(base_days * cfg["days_factor"]))
            plans.append(
                QuotePlan(
                    tier=tier,
                    label=cfg["label"],
                    description=cfg["description"],
                    success_rate=cfg["success_rate"],
                    price=price,
                    delivery_days=days,
                    deposit=round(price * DEPOSIT_RATIO, 2),
                )
            )
        return plans

    # ------------------------------------------------------------------
    # 契约生命周期
    # ------------------------------------------------------------------
    def create(
        self,
        requester_id: str,
        requirement_text: str,
        base_price: float | None = None,
        tenant_id: str | None = None,
    ) -> OutcomeContract:
        if tenant_id is not None:
            from skillos.market.tenants import TenantService

            try:
                tenant = TenantService(self._db).get(tenant_id)
            except ValueError:
                raise ValueError(f"Tenant not found: {tenant_id}") from None
            if tenant.status != "active":
                raise ValueError(f"Tenant is not active: {tenant_id} (status={tenant.status})")
        deliverables = self.decompose_requirement(requirement_text)
        now = datetime.now(timezone.utc)
        base = base_price if base_price and base_price > 0 else (len(deliverables) or 1) * BASE_PRICE_PER_DELIVERABLE
        model = OutcomeContractModel(
            id=f"ctr-{uuid.uuid4().hex[:12]}",
            requester_id=requester_id,
            tenant_id=tenant_id,
            contractor_id="",
            tier=Tier.BALANCED,
            requirement_text=requirement_text,
            deliverables=[d.__dict__ for d in deliverables],
            base_price=round(base, 2),
            price=0.0,
            currency="CNY",
            deposit=0.0,
            deposit_status="held",
            evidence_hash=None,
            evidence_risk=None,
            success_rate_commitment=0.0,
            status=OutcomeContractStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        self._db.flush()
        log_audit(
            AuditEventType.SKILL_REGISTERED,
            requester_id,
            model.id,
            "Create outcome contract (draft)",
            {"deliverables": len(deliverables), "requirement": requirement_text[:120]},
        )
        return OutcomeContract.from_orm(model)

    def select_tier(self, contract_id: str, tier: str, base_price: float | None = None) -> OutcomeContract:
        model = self._require(contract_id)
        if model.status != OutcomeContractStatus.DRAFT:
            raise ValueError(f"Only draft contracts can select tier, current: {model.status}")
        if tier not in TIER_CONFIG:
            raise ValueError(f"Invalid tier: {tier}")

        base = model.base_price if model.base_price and model.base_price > 0 else None
        plan = next(p for p in self.generate_plans(model.requirement_text, base) if p.tier == tier)
        now = datetime.now(timezone.utc)
        model.tier = tier
        model.price = plan.price
        model.deposit = plan.deposit
        model.success_rate_commitment = plan.success_rate
        model.deadline = now + timedelta(days=plan.delivery_days)
        model.status = OutcomeContractStatus.OPEN
        model.updated_at = now
        self._db.flush()
        log_audit(
            AuditEventType.SKILL_PUBLISHED,
            model.requester_id,
            contract_id,
            "Select tier, contract open",
            {"tier": tier, "price": plan.price, "success_rate": plan.success_rate},
        )
        return OutcomeContract.from_orm(model)

    def sign(self, contract_id: str, contractor_id: str) -> OutcomeContract:
        """签约开工（open → in_progress）。contractor_id 为项目长。"""
        model = self._require(contract_id)
        if model.status != OutcomeContractStatus.OPEN:
            raise ValueError(f"Only open contracts can be signed, current: {model.status}")
        model.contractor_id = contractor_id
        model.status = OutcomeContractStatus.IN_PROGRESS
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        log_audit(
            AuditEventType.SESSION_CREATED,
            contractor_id,
            contract_id,
            "Contract signed, work in progress",
            {"contractor": contractor_id, "deposit": model.deposit},
        )
        return OutcomeContract.from_orm(model)

    def submit_delivery(
        self,
        contract_id: str,
        evidence_text: str = "",
        hallucination_detector: Any | None = None,
    ) -> OutcomeContract:
        """项目长提交交付（in_progress → submitted）。

        L3 存证合规：交付物证据强制过 HallucinationDetector，风险超阈值拒绝提交；
        通过后记录 evidence_hash + evidence_risk，并写入审计日志（不可抵赖）。
        """
        model = self._require(contract_id)
        if model.status != OutcomeContractStatus.IN_PROGRESS:
            raise ValueError(f"Only in-progress contracts can submit, current: {model.status}")

        detector = hallucination_detector
        if detector is None:
            from skillos.security.hallucination_detector import HallucinationDetector

            detector = HallucinationDetector()
        risk = detector.analyze_output(evidence_text) if evidence_text else None
        if risk is not None and risk.risk >= 3:  # HIGH/CRITICAL 拒绝
            logger.warning(
                "Delivery evidence rejected for %s (risk=%s, score=%.2f)",
                contract_id,
                risk.risk.name,
                risk.score,
            )
            raise ValueError(
                f"Evidence failed compliance check (risk={risk.risk.name}, score={risk.score:.2f})"
            )

        evidence_hash = ""
        if evidence_text:
            import hashlib

            evidence_hash = hashlib.sha256(evidence_text.encode("utf-8")).hexdigest()[:32]
        model.evidence_hash = evidence_hash or None
        model.evidence_risk = risk.score if risk is not None else None
        model.status = OutcomeContractStatus.SUBMITTED
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        log_audit(
            AuditEventType.SKILL_EXECUTED,
            model.contractor_id,
            contract_id,
            "Submit delivery (evidence preserved)",
            {"evidence_hash": evidence_hash, "evidence_risk": model.evidence_risk},
        )
        return OutcomeContract.from_orm(model)

    def confirm_delivery(self, contract_id: str, accepted: bool) -> OutcomeContract:
        """需求方验收（submitted → work_completed / disputed）。验收即责任转移。"""
        model = self._require(contract_id)
        if model.status != OutcomeContractStatus.SUBMITTED:
            raise ValueError(f"Only submitted contracts can be confirmed, current: {model.status}")
        model.status = OutcomeContractStatus.WORK_COMPLETED if accepted else OutcomeContractStatus.DISPUTED
        model.deposit_status = "released" if accepted else "held"
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        log_audit(
            AuditEventType.SESSION_COMPLETED,
            model.requester_id,
            contract_id,
            "Delivery confirmed" if accepted else "Delivery disputed",
            {"accepted": accepted},
        )
        return OutcomeContract.from_orm(model)

    def add_tip(self, contract_id: str, requester_id: str, ratio: float) -> Tip:
        """超预期小费（work_completed 后）。比例限制 10%~20%，按贡献分配。"""
        if not (TIP_MIN_RATIO <= ratio <= TIP_MAX_RATIO):
            raise ValueError(f"Tip ratio must be within {TIP_MIN_RATIO}~{TIP_MAX_RATIO}")

        model = self._require(contract_id)
        if model.status not in (OutcomeContractStatus.WORK_COMPLETED, OutcomeContractStatus.PAID):
            raise ValueError(f"Tip only allowed after work completed, current: {model.status}")
        if requester_id != model.requester_id:
            raise ValueError("Only the requester can add a tip")

        amount = round(model.price * ratio, 2)
        members = self._team_members(model.id)
        if members:
            lead_share = round(amount * TIP_LEAD_SHARE_RATIO, 2)
            author_share = round(amount * TIP_LEAD_SHARE_RATIO / max(len(members), 1), 2)
            distributions = [{"member_id": model.contractor_id, "role": "lead", "amount": lead_share}]
            distributions += [{"member_id": m.member_id, "role": m.role, "amount": author_share} for m in members]
        else:
            distributions = [{"member_id": model.contractor_id, "role": "lead", "amount": amount}]

        tip = TipModel(
            id=f"tip-{uuid.uuid4().hex[:12]}",
            contract_id=contract_id,
            requester_id=requester_id,
            amount=amount,
            ratio=ratio,
            distributions=distributions,
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(tip)
        self._db.flush()
        log_audit(AuditEventType.SETTLEMENT_SUBMITTED, requester_id, contract_id, "Tip added", {"amount": amount})
        return Tip.from_orm(tip)

    def settle(self, contract_id: str) -> dict[str, Any]:
        """按成果价结算（work_completed → paid）。复用 5/25/70 记账。"""
        model = self._require(contract_id)
        if model.status != OutcomeContractStatus.WORK_COMPLETED:
            raise ValueError(f"Only completed contracts can settle, current: {model.status}")
        if model.price <= 0:
            raise ValueError("Contract price must be > 0 before settle")

        record = self._dist_engine.distribute(
            SkillCall(
                skill_id=f"contract:{contract_id}",
                caller_id=model.contractor_id,
                input_data={"contract_id": contract_id, "tier": model.tier},
                output_data={"status": "delivered", "deliverables": len(model.deliverables or [])},
                revenue_usd=model.price,
                status="settled",
            )
        )
        model.status = OutcomeContractStatus.PAID
        model.updated_at = datetime.now(timezone.utc)
        model.deposit_status = "released"
        self._db.flush()
        log_audit(
            AuditEventType.SETTLEMENT_TRIGGERED,
            model.requester_id,
            contract_id,
            "Settle outcome contract (deposit released)",
            {"amount": model.price, "deposit": model.deposit, "deposit_status": "released"},
        )
        # SLO 埋点（M9-P2）：结算作为 negmarket_api 可用性观测点
        _record_settle_metric(success=True)
        return {
            "contract_id": contract_id,
            "amount": model.price,
            "platform_fee": record.platform_fee,
            "ecosystem_fee": record.ecosystem_fee,
            "contributor_pool": record.contributor_pool,
            "deposit_status": "released",
        }

    def cancel(self, contract_id: str) -> OutcomeContract:
        model = self._require(contract_id)
        if model.status not in (OutcomeContractStatus.DRAFT, OutcomeContractStatus.OPEN):
            raise ValueError(f"Only draft/open contracts can be cancelled, current: {model.status}")
        model.status = OutcomeContractStatus.CANCELLED
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return OutcomeContract.from_orm(model)

    def arbitrate(self, contract_id: str, votes: dict[str, str]) -> dict[str, Any]:
        """L4 仲裁：disputed 争议走 ByzantineConsensus 多方验证。

        votes: {validator_id: "approve"/"reject"}。判定结果：
          - 达到 APPROVE 门限 → 维持交付（work_completed），保证金释放
          - 达到 REJECT 门限 → 判定违约（cancelled），保证金扣留（forfeited）
          - 未达门限/票未满 → 维持 disputed，等待外部仲裁

        C4 修复：强制最少票数（≥ MIN_ARBITRATION_VOTES），且验证者不得为争议双方
        （requester / contractor），防止单方操纵仲裁结果。
        """
        model = self._require(contract_id)
        if model.status != OutcomeContractStatus.DISPUTED:
            raise ValueError(f"Only disputed contracts can be arbitrated, current: {model.status}")
        if not votes:
            raise ValueError("votes must not be empty")
        if len(votes) < MIN_ARBITRATION_VOTES:
            raise ValueError(
                f"Arbitration requires at least {MIN_ARBITRATION_VOTES} validators, "
                f"received {len(votes)}"
            )
        conflicting = {model.requester_id, model.contractor_id} & set(votes)
        if conflicting:
            raise ValueError(
                f"Disputing parties cannot arbitrate: {sorted(conflicting)}"
            )

        from skillos.collaboration.consensus import ByzantineConsensus, VoteValue

        agents = list(votes)
        consensus = ByzantineConsensus(total_agents=len(agents))
        proposal_id = consensus.propose(agent_id=model.requester_id, data={"contract_id": contract_id})
        for agent_id, value in votes.items():
            try:
                consensus.vote(proposal_id, agent_id, VoteValue(value))
            except ValueError:
                raise ValueError(f"Invalid vote value: {value}") from None

        result = consensus.finalize(proposal_id)
        now = datetime.now(timezone.utc)
        decision: str = "pending"
        if result.final_decision == VoteValue.APPROVE:
            model.status = OutcomeContractStatus.WORK_COMPLETED
            model.deposit_status = "released"
            decision = "approve"
        elif result.final_decision == VoteValue.REJECT:
            model.status = OutcomeContractStatus.CANCELLED
            model.deposit_status = "forfeited"
            decision = "reject"
        else:
            decision = "pending"

        model.updated_at = now
        self._db.flush()
        log_audit(
            AuditEventType.SESSION_COMPLETED,
            model.requester_id,
            contract_id,
            "Arbitration result",
            {
                "decision": decision,
                "required_agreements": result.required_agreements,
                "total_agents": result.total_agents,
                "votes": votes,
            },
        )
        return {
            "contract_id": contract_id,
            "status": model.status,
            "decision": decision,
            "deposit_status": model.deposit_status,
            "required_agreements": result.required_agreements,
            "total_agents": result.total_agents,
        }

    def get(self, contract_id: str) -> OutcomeContract | None:
        model = self._db.query(OutcomeContractModel).filter(OutcomeContractModel.id == contract_id).first()
        return OutcomeContract.from_orm(model) if model else None

    def get_tips(self, contract_id: str) -> list[Tip]:
        rows = self._db.query(TipModel).filter(TipModel.contract_id == contract_id).all()
        return [Tip.from_orm(r) for r in rows]

    def list_open(self, page: int = 1, page_size: int = 20) -> list[OutcomeContract]:
        """列出可承接的 open 契约（供外部 Agent 构建者浏览承接）。"""
        rows = (
            self._db.query(OutcomeContractModel)
            .filter(OutcomeContractModel.status == OutcomeContractStatus.OPEN)
            .order_by(OutcomeContractModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [OutcomeContract.from_orm(r) for r in rows]

    def list_by_contractor(self, contractor_id: str, page: int = 1, page_size: int = 20) -> list[OutcomeContract]:
        """列出某项目长承接的契约（供外部 Agent 查询自己的执行记录）。"""
        rows = (
            self._db.query(OutcomeContractModel)
            .filter(OutcomeContractModel.contractor_id == contractor_id)
            .order_by(OutcomeContractModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [OutcomeContract.from_orm(r) for r in rows]

    def create_service_team(self, contract_id: str, lead_id: str, members: list[dict[str, Any]]) -> str:
        """创建服务团队（MVP 平台自营：平台当项目长，技能作者按 share_ratio 分成）。

        C3 修复：校验 share_ratio ∈ [0,1] 且合计 ≤ 1.0，
        防止负金额/超额分成绕过出款防超发校验（generate_for_contract 的 C3 守卫）。
        """
        contract = self._require(contract_id)
        share_total = 0.0
        for m in members:
            ratio = float(m.get("share_ratio", 0.0))
            if not (0.0 <= ratio <= 1.0):
                raise ValueError(f"share_ratio must be within [0, 1], got {ratio}")
            share_total += ratio
        if share_total > 1.0:
            raise ValueError(
                f"sum of share_ratio must be ≤ 1.0 (70% contributor pool), got {round(share_total, 4)}"
            )
        team = ServiceTeamModel(
            id=f"team-{uuid.uuid4().hex[:12]}",
            contract_id=contract.id,
            lead_id=lead_id,
            status="assembling",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._db.add(team)
        self._db.flush()
        for m in members:
            self._db.add(
                ServiceTeamMemberModel(
                    id=f"tm-{uuid.uuid4().hex[:12]}",
                    team_id=team.id,
                    member_id=m["member_id"],
                    role=m.get("role", "skill_author"),
                    share_ratio=m.get("share_ratio", 0.0),
                    created_at=datetime.now(timezone.utc),
                )
            )
        self._db.flush()
        return team.id

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _require(self, contract_id: str) -> OutcomeContractModel:
        model = self._db.query(OutcomeContractModel).filter(OutcomeContractModel.id == contract_id).first()
        if model is None:
            raise ValueError(f"Contract not found: {contract_id}")
        return model

    def _team_members(self, contract_id: str) -> list[ServiceTeamMemberModel]:
        team = (
            self._db.query(ServiceTeamModel)
            .filter(ServiceTeamModel.contract_id == contract_id)
            .first()
        )
        if team is None:
            return []
        return (
            self._db.query(ServiceTeamMemberModel)
            .filter(ServiceTeamMemberModel.team_id == team.id)
            .all()
        )
