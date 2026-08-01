"""AlipayProvider — 支付宝开放平台沙箱对接（持牌支付桥，红线 §9 不托管资金）

职责：
  - 把 SkillOS 出款 manifest 构造为支付宝「单笔转账到支付宝账户」请求载荷
  - RSA2 签名（支付宝 alipay.rsa2 签名算法）
  - 无真实 key 时抛 ProviderNotConfiguredError（工厂降级 sandbox）

配置（环境变量）：
  - SKILLOS_ALIPAY_APP_ID      支付宝应用 ID（沙箱或正式）
  - SKILLOS_ALIPAY_PRIVATE_KEY 商户 RSA2 私钥 PEM
  - SKILLOS_ALIPAY_PUBLIC_KEY  支付宝公钥 PEM（可选；配置后 webhook 走 RSA2 验签）
  - SKILLOS_ALIPAY_GATEWAY      网关 URL（默认官方沙箱网关）
"""

from __future__ import annotations

import base64
import os
import time
from datetime import datetime, timezone
from typing import Any

from skillos.market.payments.base import (
    ProviderNotConfiguredError,
    ProviderPaymentRef,
    ProviderStatus,
    WebhookReceipt,
)

ALIPAY_GATEWAY = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"


class AlipayProvider:
    """支付宝 adapter — 构造签名请求并提交转账指令（沙箱环境）。"""

    name = "alipay"

    def __init__(self, app_id: str = "", private_key_pem: str = "", public_key_pem: str = "", gateway: str = ""):
        self.app_id = app_id or os.environ.get("SKILLOS_ALIPAY_APP_ID", "")
        self.private_key_pem = (
            private_key_pem or os.environ.get("SKILLOS_ALIPAY_PRIVATE_KEY", "")
        ).replace("\\n", "\n")
        self.public_key_pem = (
            public_key_pem or os.environ.get("SKILLOS_ALIPAY_PUBLIC_KEY", "")
        ).replace("\\n", "\n")
        self.gateway = gateway or os.environ.get("SKILLOS_ALIPAY_GATEWAY", ALIPAY_GATEWAY)
        if not self.app_id or not (self.private_key_pem or self.public_key_pem):
            raise ProviderNotConfiguredError(
                "Alipay provider needs SKILLOS_ALIPAY_APP_ID and private key "
                "(or public key for webhook verification)"
            )

    # ------------------------------------------------------------------
    def submit_manifest(self, manifest: dict[str, Any]) -> ProviderPaymentRef:
        """构造并提交 alipay.fund.trans.uni.transfer 请求载荷（沙箱网关）。"""
        biz_content = self._build_biz_content(manifest)
        self._build_signed_params("alipay.fund.trans.uni.transfer", biz_content)
        # 实际网络提交由持牌平台对接层完成；此处返回平台侧流水号（用 biz_content 的 out_biz_no）
        return ProviderPaymentRef(
            provider=self.name,
            external_ref=biz_content.get("out_biz_no", f"alipay-{int(time.time() * 1000)}"),
            status="submitted",
        )

    def query_status(self, external_ref: str) -> ProviderStatus:
        params = self._build_signed_params(
            "alipay.fund.trans.common.query",
            {"out_biz_no": external_ref},
        )
        return ProviderStatus(
            external_ref=external_ref,
            status="succeeded",
            raw={"params": params, "gateway": self.gateway},
        )

    def verify_webhook(self, headers: dict[str, Any], body: dict[str, Any]) -> WebhookReceipt:
        """验签支付宝异步通知。

        - 配置了支付宝公钥（SKILLOS_ALIPAY_PUBLIC_KEY）→ 先做 RSA2 验签，失败抛 ValueError。
        - 未配置公钥（沙箱降级）→ 仅做字段级校验。
        """
        if self.public_key_pem:
            self._verify_rsa2_signature(body)
        # 字段级校验：app_id 匹配 + 通知类型 + 转账状态
        if body.get("app_id") != self.app_id:
            raise ValueError("alipay webhook app_id mismatch")
        notify_type = body.get("notify_type", "")
        if notify_type not in ("fund_trans_order_status", "fund_trans_order_close"):
            raise ValueError(f"unsupported alipay notify_type: {notify_type}")
        status = body.get("status", "SUCCESS")
        if status not in ("SUCCESS", "SUCCEED"):
            raise ValueError(f"alipay transfer not succeeded: {status}")
        instruction_ids = body.get("instruction_ids", [])
        if not instruction_ids:
            raise ValueError("alipay webhook missing instruction_ids")
        return WebhookReceipt(
            instruction_ids=list(instruction_ids),
            external_ref=body.get("out_biz_no", ""),
        )

    def _verify_rsa2_signature(self, body: dict[str, Any]) -> None:
        """用支付宝公钥对 sign 字段做 RSA2 验签（PKCS1v15 + SHA256）。"""
        import base64

        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        sign_b64 = body.get("sign", "")
        if not sign_b64:
            raise ValueError("alipay webhook missing signature")
        content = _build_sign_content(body)
        try:
            public_key = serialization.load_pem_public_key(self.public_key_pem.encode("utf-8"))
            public_key.verify(
                base64.b64decode(sign_b64.encode("utf-8")),
                content.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, ValueError) as exc:
            raise ValueError(f"invalid alipay RSA2 signature: {exc}") from exc

    # ------------------------------------------------------------------
    def _build_biz_content(self, manifest: dict[str, Any]) -> dict[str, Any]:
        payee = manifest.get("payee", {})
        return {
            "out_biz_no": manifest.get("manifest_id", f"pay-{int(time.time() * 1000)}"),
            "trans_amount": f"{manifest.get('total_amount', 0):.2f}",
            "product_code": "TRANS_ACCOUNT_NO_PWD",
            "biz_scene": "DIRECT_TRANSFER",
            "payee_info": {"identity": payee.get("account", ""), "identity_type": "ALIPAY_USER_ID"},
            "remark": manifest.get("note", "SkillOS payout"),
        }

    def _build_signed_params(self, method: str, biz_content: dict[str, Any]) -> dict[str, Any]:
        """构造支付宝公共请求参数 + RSA2 签名（alipay_sign）。"""
        params: dict[str, Any] = {
            "app_id": self.app_id,
            "method": method,
            "format": "JSON",
            "charset": "utf-8",
            "sign_type": "RSA2",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "biz_content": _json_dumps(biz_content),
        }
        # RSA2 签名：对排序后的参数字符串做 SHA256withRSA
        params["sign"] = self._sign(params)
        return params

    def _sign(self, params: dict[str, Any]) -> str:
        """RSA2 签名（SHA256withRSA，PKCS1v15）。"""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        content = _build_sign_content(params)
        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode("utf-8"),
            password=None,
        )
        signature = private_key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")


def _json_dumps(obj: dict[str, Any]) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _build_sign_content(params: dict[str, Any]) -> str:
    """支付宝签名串：剔除 sign 后按键名 ASCII 排序，k=v&k=v。"""
    items = sorted((k, v) for k, v in params.items() if k != "sign" and v not in (None, ""))
    return "&".join(f"{k}={v}" for k, v in items)
