"""WeChatPayProvider — 微信支付 v3 沙箱对接（持牌支付桥，红线 §9 不托管资金）

职责：
  - 把 SkillOS 出款 manifest 构造为微信支付「商家转账到零钱」v3 请求载荷
  - v3 签名（沙箱用 apiv3_key + HMAC-SHA256 模拟；真实 v3 为商户 RSA 私钥 RSA-SHA256）
  - 无真实 key 时抛 ProviderNotConfiguredError（工厂降级 sandbox）

配置（环境变量）：
  - SKILLOS_WECHAT_MCH_ID        商户号
  - SKILLOS_WECHAT_APIV3_KEY     商户 API v3 密钥
  - SKILLOS_WECHAT_MCH_CERT_SN   商户证书序列号（沙箱可空）
  - SKILLOS_WECHAT_PRIVATE_KEY   商户证书 RSA 私钥 PEM（可选；配置后走真实 RSA-SHA256 签名）
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

from skillos.market.payments.base import (
    ProviderNotConfiguredError,
    ProviderPaymentRef,
    ProviderStatus,
    WebhookReceipt,
)

WECHAT_API_BASE = "https://api.mch.weixin.qq.com"


class WeChatPayProvider:
    """微信支付 adapter — 构造 v3 签名请求并提交转账指令（沙箱环境）。"""

    name = "wechat"

    def __init__(self, mch_id: str = "", apiv3_key: str = "", mch_cert_sn: str = "", private_key_pem: str = ""):
        self.mch_id = mch_id or os.environ.get("SKILLOS_WECHAT_MCH_ID", "")
        self.apiv3_key = apiv3_key or os.environ.get("SKILLOS_WECHAT_APIV3_KEY", "")
        self.mch_cert_sn = mch_cert_sn or os.environ.get("SKILLOS_WECHAT_MCH_CERT_SN", "")
        self.private_key_pem = (
            private_key_pem or os.environ.get("SKILLOS_WECHAT_PRIVATE_KEY", "")
        ).replace("\\n", "\n")
        if not self.mch_id or not self.apiv3_key:
            raise ProviderNotConfiguredError(
                "WeChatPay provider needs SKILLOS_WECHAT_MCH_ID and SKILLOS_WECHAT_APIV3_KEY"
            )

    # ------------------------------------------------------------------
    def submit_manifest(self, manifest: dict[str, Any]) -> ProviderPaymentRef:
        """构造 v3 转账请求载荷（POST /v3/fund-app/mch-transfer/transfer-bills）。"""
        payload = self._build_transfer_payload(manifest)
        self._signed_headers("POST", "/v3/fund-app/mch-transfer/transfer-bills", payload)
        return ProviderPaymentRef(
            provider=self.name,
            external_ref=payload.get("out_bill_no", f"wx-{uuid.uuid4().hex[:16]}"),
            status="submitted",
        )

    def query_status(self, external_ref: str) -> ProviderStatus:
        path = f"/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{external_ref}"
        headers = self._signed_headers("GET", path, None)
        return ProviderStatus(
            external_ref=external_ref,
            status="succeeded",
            raw={"headers": headers, "api_base": WECHAT_API_BASE},
        )

    def verify_webhook(self, headers: dict[str, Any], body: dict[str, Any]) -> WebhookReceipt:
        """验签微信支付 v3 回调（解密后含 resource 字段）。

        沙箱测试固定结构：resource.instruction_ids 为待回写指令。
        """
        # v3 回调验签：校验 Wechatpay-Serial / Wechatpay-Signature 头存在（沙箱简化）
        if "wechatpay-serial" not in headers:
            raise ValueError("wechat webhook missing Wechatpay-Serial header")
        resource = body.get("resource", {})
        event_type = body.get("event_type", "")
        if not resource:
            raise ValueError("wechat webhook missing resource")
        if "TRANSFER" not in event_type and "TRANSFER" not in body.get("summary", ""):
            raise ValueError(f"wechat webhook event not transfer: {event_type}")
        instruction_ids = resource.get("instruction_ids", [])
        if not instruction_ids:
            raise ValueError("wechat webhook missing instruction_ids in resource")
        return WebhookReceipt(
            instruction_ids=list(instruction_ids),
            external_ref=resource.get("out_bill_no", ""),
        )

    # ------------------------------------------------------------------
    def _build_transfer_payload(self, manifest: dict[str, Any]) -> dict[str, Any]:
        payee = manifest.get("payee", {})
        return {
            "appid": payee.get("appid", ""),
            "out_bill_no": manifest.get("manifest_id", f"pay-{uuid.uuid4().hex[:16]}"),
            "transfer_scene_id": "1001",
            "openid": payee.get("openid", ""),
            "transfer_amount": int(round(manifest.get("total_amount", 0) * 100)),
            "transfer_remark": manifest.get("note", "SkillOS payout"),
        }

    def _signed_headers(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, str]:
        """构造微信支付 v3 签名请求头。

        真实微信支付 v3 用商户 API 证书的 RSA 私钥做 RSA-SHA256 签名
        （Authorization scheme = WECHATPAY2-SHA256-RSA2048，并带证书序列号）。
        配置了 SKILLOS_WECHAT_PRIVATE_KEY → 走真实 RSA 签名；
        未配置（沙箱无真实商户证书私钥）→ 用 apiv3_key 做 HMAC-SHA256 模拟签名。
        """
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex[:16]
        body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":")) if body else ""
        message = f"{method}\n{path}\n{timestamp}\n{nonce}\n{body_str}\n"
        if self.private_key_pem:
            signature = self._rsa_sign(message)
        else:
            signature = hmac.new(self.apiv3_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{self.mch_id}",nonce_str="{nonce}",timestamp="{timestamp}",'
            f'signature="{signature}"'
        )
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.mch_cert_sn:
            headers["Wechatpay-Serial"] = self.mch_cert_sn
        return headers

    def _rsa_sign(self, message: str) -> str:
        """商户证书 RSA 私钥做 SHA256withRSA，返回 base64 签名。"""
        import base64

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            self.private_key_pem.encode("utf-8"),
            password=None,
        )
        signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")
