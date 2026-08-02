"""SkillOS Payments — 持牌支付 manifest 对接层（红线 §9 不托管资金）

导出：
  - get_provider(): 工厂（未配置/无 key → SandboxProvider）
  - submit_contract_payout(): 已结算契约 → 出款指令 → 提交持牌平台 → 回写 external_ref
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from skillos.market.payments.base import (
    PaymentProvider,
    ProviderNotConfiguredError,
    ProviderPaymentRef,
    ProviderStatus,
    get_provider,
)

__all__ = [
    "PaymentProvider",
    "ProviderNotConfiguredError",
    "ProviderPaymentRef",
    "ProviderStatus",
    "get_provider",
    "submit_contract_payout",
]


def submit_contract_payout(
    db_session: Session,
    contract_id: str,
    provider: PaymentProvider | None = None,
) -> dict[str, Any]:
    """已结算契约 → 出款 manifest → 提交持牌平台 → 回写每条指令 external_ref。

    C7 修复：以契约出款指令状态为幂等键——若任一指令已提交/已执行，拒绝重复
    提交，防止对真实持牌平台重复划转资金。

    Args:
        db_session: SQLAlchemy 会话
        contract_id: 已 paid 的契约 ID
        provider: 目标持牌 provider（None 时用 get_provider()）

    Returns:
        {"provider", "external_ref", "status", "instructions"}

    Raises:
        ValueError: 契约非 paid、指令已提交/已执行、契约不存在
    """
    from skillos.market.payouts import PayoutService

    provider = provider or get_provider()
    payouts = PayoutService(db_session)
    manifest = payouts.export_manifest(contract_id)

    # C7 幂等防重：已提交/已执行的指令不允许再次提交
    for instruction in manifest["instructions"]:
        if instruction["status"] in ("submitted", "executed"):
            raise ValueError(
                f"Payout already submitted for contract {contract_id} "
                f"(instruction {instruction['instruction_id']} status={instruction['status']})"
            )

    ref = provider.submit_manifest(manifest)

    updated = []
    for instruction in manifest["instructions"]:
        row = payouts.mark_executed(instruction["instruction_id"], external_ref=ref.external_ref)
        updated.append(
            {
                "instruction_id": row.id,
                "payee_id": row.payee_id,
                "role": row.role,
                "amount": row.amount,
                "status": row.status,
                "external_ref": row.external_ref,
            }
        )

    return {
        "provider": ref.provider,
        "external_ref": ref.external_ref,
        "status": ref.status,
        "instructions": updated,
    }
