"""Payment Provider 抽象层 — 持牌支付 manifest 对接（红线 §9 不托管资金）

职责：
  - 定义 PaymentProvider 协议：提交出款指令 / 查询状态 / 验签 webhook
  - 工厂 get_provider()：根据环境变量选择 adapter，无 key 一律降级 SandboxProvider
  - 只做「记账指令提交」协议对接，真实法币划转由持牌平台执行

红线：
  - 不托管真实资金：adapter 不持有/划转资金，只提交记账 manifest
  - 无 key 环境一律 sandbox：绝不用测试 key 冒充真实交易
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ProviderPaymentRef:
    """持牌平台侧支付引用。"""

    provider: str
    external_ref: str
    status: str


@dataclass
class ProviderStatus:
    """出款指令在持牌平台侧的状态查询结果。"""

    external_ref: str
    status: str  # submitted / processing / succeeded / failed
    raw: dict[str, Any]


@dataclass
class WebhookReceipt:
    """持牌平台回执验签结果：已确认成功的指令 + 平台侧流水号。

    external_ref 为真实平台回执中的流水单号，由各 adapter 从平台特有字段
    （支付宝 out_biz_no / 微信 out_bill_no / sandbox external_ref）映射而来。
    """

    instruction_ids: list[str]
    external_ref: str = ""


class ProviderNotConfiguredError(RuntimeError):
    """adapter 需要真实平台密钥但未配置（工厂会据此降级 sandbox）。"""


class PaymentProvider(Protocol):
    """持牌支付 provider 协议。"""

    name: str

    def submit_manifest(self, manifest: dict[str, Any]) -> ProviderPaymentRef:
        """把出款 manifest 提交给持牌平台，返回平台侧流水号。"""

    def query_status(self, external_ref: str) -> ProviderStatus:
        """查询某笔出款指令在持牌平台侧的状态。"""

    def verify_webhook(
        self,
        headers: dict[str, Any],
        body: dict[str, Any],
        raw_body: str | None = None,
    ) -> WebhookReceipt:
        """验签持牌平台回执，返回已确认成功的 instruction 列表与平台侧流水号。

        raw_body 为原始请求体字符串（部分平台对原始字节验签），可为 None。
        验签失败应抛异常（由调用方映射为 401）。
        """


def get_provider(name: str = "") -> PaymentProvider:
    """工厂：返回配置的持牌 adapter；未配置 / 无 key → SandboxProvider。

    选择顺序：
      1. 显式传入 name
      2. 环境变量 SKILLOS_PAYMENT_PROVIDER
      3. 未配置 → sandbox（保证无 key 环境全链路可测）
    """
    from skillos.market.payments.sandbox import SandboxProvider

    provider_name = name or os.environ.get("SKILLOS_PAYMENT_PROVIDER", "").strip().lower()

    if provider_name in ("", "sandbox"):
        return SandboxProvider()

    if provider_name in ("alipay", "支付宝"):
        from skillos.market.payments.alipay import AlipayProvider

        try:
            return AlipayProvider()
        except ProviderNotConfiguredError:
            return SandboxProvider()

    if provider_name in ("wechat", "wechatpay", "wechat_pay", "微信"):
        from skillos.market.payments.wechat import WeChatPayProvider

        try:
            return WeChatPayProvider()
        except ProviderNotConfiguredError:
            return SandboxProvider()

    raise ValueError(f"Unknown payment provider: {provider_name}")
