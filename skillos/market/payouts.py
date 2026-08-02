"""Payout Service — 出款指令导出（持牌支付桥接层）

职责：
  - 已结算契约（paid）生成出款指令：项目长（contractor）结算款 + 技能作者分成 + 小费分配
  - 汇总为下游持牌平台可消费的 outbound manifest（JSON），实际法币划转由持牌方执行
  - 不托管真实资金（红线 §9）：本服务只产出记账指令，不做资金存储/划转

设计意图：
  - 商业闭环的最后一段桥：SkillOS 记账层 → 持牌支付平台
  - manifest 幂等：同一契约重复导出不产生重复指令（按 contract_id 去重）
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.audit import AuditEventType, log_audit
from skillos.db.models import OutcomeContractModel, PayoutInstructionModel, ServiceTeamMemberModel, ServiceTeamModel
from skillos.market.settlement import CONTRIBUTOR_PAYOUT_RATE, PLATFORM_FEE_RATE
from skillos.market.tenant_pools import TenantPoolService
from skillos.market.tenants import TenantService

logger = logging.getLogger(__name__)


class PayoutLimitExceededError(Exception):
    """租户出款限额不足时抛出（配额/计费隔离，M9）。"""


@dataclass
class PayoutInstruction:
    id: str
    contract_id: str
    payee_id: str
    role: str
    amount: float
    currency: str
    source: str
    status: str
    external_ref: str
    created_at: datetime

    @classmethod
    def from_orm(cls, model: PayoutInstructionModel) -> "PayoutInstruction":
        return cls(
            id=model.id,
            contract_id=model.contract_id,
            payee_id=model.payee_id,
            role=model.role,
            amount=model.amount,
            currency=model.currency,
            source=model.source,
            status=model.status,
            external_ref=model.external_ref,
            created_at=model.created_at,
        )


class PayoutService:
    """出款指令服务 — 把已结算契约转化为下游持牌平台可执行的出款指令。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def generate_for_contract(self, contract_id: str) -> list[PayoutInstruction]:
        """为已结算契约生成出款指令（幂等：已生成过则直接返回现有指令）。"""
        existing = self._db.query(PayoutInstructionModel).filter(
            PayoutInstructionModel.contract_id == contract_id
        ).all()
        if existing:
            return [PayoutInstruction.from_orm(m) for m in existing]

        contract = self._db.query(OutcomeContractModel).filter(OutcomeContractModel.id == contract_id).first()
        if contract is None:
            raise ValueError(f"Contract not found: {contract_id}")
        if contract.status != "paid":
            raise ValueError(f"Only paid contracts can generate payouts, current: {contract.status}")

        # 租户出款限额校验（M9 + M11）：先自有配额，再池共享余额联合判断
        if contract.tenant_id:
            tenant_svc = TenantService(self._db)
            usage = tenant_svc.get_payout_usage(contract.tenant_id)
            own_over = usage["limit"] > 0 and usage["used"] + contract.price > usage["limit"]
            if own_over:
                # 自有超限 → 尝试从共享池借用
                pool_svc = TenantPoolService(self._db)
                rel = pool_svc.pool_for_tenant(contract.tenant_id)
                if rel is None or not pool_svc.consume(rel[0].pool_id, contract.tenant_id, contract.price):
                    raise PayoutLimitExceededError(
                        f"Tenant payout limit exceeded: {contract.tenant_id} "
                        f"used={usage['used']} + price={contract.price} > limit={usage['limit']}"
                    )

        now = datetime.now(timezone.utc)
        instructions: list[PayoutInstruction] = []

        # 技能作者分成（service_team_members 的 share_ratio）——先从 70% 贡献池划拨
        members = self._team_members(contract_id)
        author_share_total = round(sum(member.share_ratio for member in members), 6)
        # C3 纵深防御：share 超出 70% 池会令 contractor 金额变负（create_service_team 已拦截，
        # 此处兜底防止历史脏数据/绕过）
        if author_share_total > 1.0:
            raise ValueError(
                f"author share_ratio sum {author_share_total} exceeds 1.0 (contributor pool)"
            )

        # 项目长结算款：贡献池（70%）减去作者分成后归项目长，保证总额 ≤ 价格（C3 修复）
        if contract.contractor_id and contract.price > 0:
            instructions.append(
                self._add_instruction(
                    contract_id=contract_id,
                    payee_id=contract.contractor_id,
                    role="contractor",
                    amount=round(contract.price * CONTRIBUTOR_PAYOUT_RATE * (1 - author_share_total), 2),
                    currency=contract.currency,
                    source="settlement",
                    now=now,
                )
            )

        # 技能作者分成（贡献池内划拨，不额外超发）
        for member in members:
            instructions.append(
                self._add_instruction(
                    contract_id=contract_id,
                    payee_id=member.member_id,
                    role=member.role,
                    amount=round(contract.price * CONTRIBUTOR_PAYOUT_RATE * member.share_ratio, 2),
                    currency=contract.currency,
                    source="settlement",
                    now=now,
                )
            )

        # 平台协议费（5%）— 记账指令，供持牌方代收
        instructions.append(
            self._add_instruction(
                contract_id=contract_id,
                payee_id="skillos-platform",
                role="platform",
                amount=round(contract.price * PLATFORM_FEE_RATE, 2),
                currency=contract.currency,
                source="platform_fee",
                now=now,
            )
        )

        # C3 防超发：出款总额必须 ≤ 契约价（贡献池 70% + 平台费 5% ≤ 100%）
        total_payout = round(sum(i.amount for i in instructions), 2)
        if total_payout > round(contract.price, 2):
            raise ValueError(
                f"Payout total {total_payout} exceeds contract price {contract.price} "
                f"(share_ratio sum must be ≤ 1.0)"
            )

        # 租户出款用量累计（M9）：仅在首次生成时累加，幂等导出不叠加
        if contract.tenant_id:
            TenantService(self._db).add_payout_used(contract.tenant_id, contract.price)

        self._db.flush()
        log_audit(
            AuditEventType.SETTLEMENT_TRIGGERED,
            contract.requester_id,
            contract_id,
            "Generate payout instructions",
            {"instructions": len(instructions), "contract": contract_id},
        )
        return instructions

    def export_manifest(self, contract_id: str) -> dict[str, Any]:
        """导出单个契约的出款 manifest（供持牌平台消费）。"""
        instructions = self.generate_for_contract(contract_id)
        return {
            "manifest_id": f"pay-{uuid.uuid4().hex[:12]}",
            "contract_id": contract_id,
            "currency": instructions[0].currency if instructions else "CNY",
            "instructions": [self._serialize(i) for i in instructions],
            "total_amount": round(sum(i.amount for i in instructions), 2),
            "note": "记账指令：实际法币划转由下游持牌支付平台执行（不托管资金）",
        }

    def export_period_manifest(self, start: str, end: str) -> dict[str, Any]:
        """导出时间段内的全部出款指令汇总（按 created_at 过滤）。"""
        # M7：created_at 列为 naive（SQLite 读回），传入带 tz 的 ISO 会 TypeError，统一剥掉 tz。
        start_dt = datetime.fromisoformat(start).replace(tzinfo=None)
        end_dt = datetime.fromisoformat(end).replace(tzinfo=None)
        rows = (
            self._db.query(PayoutInstructionModel)
            .filter(PayoutInstructionModel.created_at >= start_dt)
            .filter(PayoutInstructionModel.created_at <= end_dt)
            .order_by(PayoutInstructionModel.created_at.asc())
            .all()
        )
        return {
            "manifest_id": f"pay-{uuid.uuid4().hex[:12]}",
            "period": {"start": start, "end": end},
            "instructions": [self._serialize(PayoutInstruction.from_orm(m)) for m in rows],
            "total_amount": round(sum(m.amount for m in rows), 2),
            "note": "记账指令：实际法币划转由下游持牌支付平台执行（不托管资金）",
        }

    def mark_executed(self, instruction_id: str, external_ref: str = "") -> PayoutInstruction:
        """标记出款指令已由持牌平台执行（下游回调）。"""
        model = self._db.query(PayoutInstructionModel).filter(
            PayoutInstructionModel.id == instruction_id
        ).first()
        if model is None:
            raise ValueError(f"Payout instruction not found: {instruction_id}")
        model.status = "executed"
        model.external_ref = external_ref or model.external_ref
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return PayoutInstruction.from_orm(model)

    def list_by_payee(self, payee_id: str) -> list[PayoutInstruction]:
        rows = (
            self._db.query(PayoutInstructionModel)
            .filter(PayoutInstructionModel.payee_id == payee_id)
            .order_by(PayoutInstructionModel.created_at.desc())
            .limit(200)
            .all()
        )
        return [PayoutInstruction.from_orm(m) for m in rows]

    # ------------------------------------------------------------------
    def _add_instruction(
        self,
        *,
        contract_id: str,
        payee_id: str,
        role: str,
        amount: float,
        currency: str,
        source: str,
        now: datetime,
    ) -> PayoutInstruction:
        model = PayoutInstructionModel(
            id=f"pay-{uuid.uuid4().hex[:12]}",
            contract_id=contract_id,
            payee_id=payee_id,
            role=role,
            amount=amount,
            currency=currency,
            source=source,
            status="pending",
            external_ref="",
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        return PayoutInstruction.from_orm(model)

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

    @staticmethod
    def _serialize(i: PayoutInstruction) -> dict[str, Any]:
        return {
            "instruction_id": i.id,
            "contract_id": i.contract_id,
            "payee_id": i.payee_id,
            "role": i.role,
            "amount": i.amount,
            "currency": i.currency,
            "source": i.source,
            "status": i.status,
            "external_ref": i.external_ref,
            "created_at": i.created_at.isoformat(),
        }
