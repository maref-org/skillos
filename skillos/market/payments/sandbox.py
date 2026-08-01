"""SandboxProvider — 本地模拟持牌支付（无 key 环境默认实现）

职责：
  - 模拟持牌平台受理出款 manifest，返回 sandbox-{uuid} 流水号
  - 模拟回执验签（固定 HMAC 测试密钥），供 webhook 端点自测
  - 保证无真实平台密钥时全链路可测（红线 §9：不触碰真实资金）

行为：
  - submit_manifest: 立即返回 succeeded（本地模拟即时到账）
  - verify_webhook: 校验 body 内 instruction_ids 非空 + X-Sandbox-Token 匹配
"""

from __future__ import annotations

import hmac
import uuid
from typing import Any

from skillos.market.payments.base import (
    ProviderPaymentRef,
    ProviderStatus,
    WebhookReceipt,
)

SANDBOX_TOKEN = "sk-sandbox-test-token"


class SandboxProvider:
    """本地模拟持牌支付 provider（默认降级实现）。"""

    name = "sandbox"

    def submit_manifest(self, manifest: dict[str, Any]) -> ProviderPaymentRef:
        return ProviderPaymentRef(
            provider=self.name,
            external_ref=f"sandbox-{uuid.uuid4().hex[:16]}",
            status="succeeded",
        )

    def query_status(self, external_ref: str) -> ProviderStatus:
        return ProviderStatus(
            external_ref=external_ref,
            status="succeeded",
            raw={"provider": self.name},
        )

    def verify_webhook(self, headers: dict[str, Any], body: dict[str, Any]) -> WebhookReceipt:
        """验签沙箱回执：X-Sandbox-Token 匹配 + instruction_ids 非空。"""
        token = headers.get("x-sandbox-token", "")
        if not hmac.compare_digest(token, SANDBOX_TOKEN):
            raise ValueError("invalid sandbox webhook token")
        instruction_ids = body.get("instruction_ids", [])
        if not instruction_ids:
            raise ValueError("webhook body missing instruction_ids")
        return WebhookReceipt(
            instruction_ids=list(instruction_ids),
            external_ref=body.get("external_ref", ""),
        )
