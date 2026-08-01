"""Tests for M6-P1 — Alipay / WeChat adapters（无 key 降级 + 签名构造）"""

import pytest

from skillos.market.payments.alipay import AlipayProvider
from skillos.market.payments.base import ProviderNotConfiguredError
from skillos.market.payments.wechat import WeChatPayProvider


class TestAlipayAdapter:
    def test_missing_key_raises(self):
        with pytest.raises(ProviderNotConfiguredError, match="SKILLOS_ALIPAY"):
            AlipayProvider(app_id="", private_key_pem="")

    def test_rsa2_signature_generation(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = (
            rsa_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            .decode("utf-8")
        )
        provider = AlipayProvider(app_id="app-test", private_key_pem=pem, gateway="https://sandbox")
        manifest = {"manifest_id": "pay-abc", "total_amount": 100.0, "payee": {"account": "u-1"}}
        ref = provider.submit_manifest(manifest)
        assert ref.provider == "alipay"
        assert ref.status == "submitted"
        assert ref.external_ref == "pay-abc"

    def test_webhook_ok(self):
        provider = AlipayProvider(
            app_id="app-test",
            private_key_pem="dummy-private-key",
            gateway="https://sandbox",
        )
        receipt = provider.verify_webhook(
            {},
            {
                "app_id": "app-test",
                "notify_type": "fund_trans_order_status",
                "status": "SUCCESS",
                "instruction_ids": ["pay-1"],
            },
        )
        assert receipt.instruction_ids == ["pay-1"]

    def test_webhook_bad_app_id(self):
        provider = AlipayProvider(app_id="app-test", private_key_pem="dummy-private-key")
        with pytest.raises(ValueError, match="app_id mismatch"):
            provider.verify_webhook({}, {"app_id": "other", "notify_type": "fund_trans_order_status"})


class TestAlipayPublicKeyVerification:
    """M7-P1.2 — 支付宝公钥 RSA2 验签（可选配置，无公钥降级字段校验）。"""

    def _provider_with_pubkey(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub_pem = (
            key.public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
        provider = AlipayProvider(app_id="app-test", public_key_pem=pub_pem)
        return key, provider

    def test_verify_webhook_requires_valid_rsa2_signature_when_pubkey_set(self):
        _, provider = self._provider_with_pubkey()
        body = {
            "app_id": "app-test",
            "notify_type": "fund_trans_order_status",
            "status": "SUCCESS",
            "instruction_ids": ["pay-1"],
        }
        with pytest.raises(ValueError, match="signature"):
            provider.verify_webhook({}, body)

    def test_verify_webhook_accepts_valid_rsa2_signature(self):
        from skillos.market.payments.alipay import _build_sign_content

        key, provider = self._provider_with_pubkey()
        body = {
            "app_id": "app-test",
            "notify_type": "fund_trans_order_status",
            "status": "SUCCESS",
            "instruction_ids": ["pay-1"],
            "out_biz_no": "alipay-real-1",
        }
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        content = _build_sign_content(body)
        sig = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        body["sign"] = __import__("base64").b64encode(sig).decode("utf-8")

        receipt = provider.verify_webhook({}, body)
        assert receipt.instruction_ids == ["pay-1"]
        assert receipt.external_ref == "alipay-real-1"

    def test_verify_webhook_rejects_tampered_signature(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        from skillos.market.payments.alipay import _build_sign_content

        key, provider = self._provider_with_pubkey()
        body = {
            "app_id": "app-test",
            "notify_type": "fund_trans_order_status",
            "status": "SUCCESS",
            "instruction_ids": ["pay-1"],
        }
        content = _build_sign_content(body)
        sig = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        body["sign"] = __import__("base64").b64encode(sig).decode("utf-8")
        body["status"] = "SUCCESS"  # 篡改字段后原签名不再有效（覆盖在签名串内）

        tampered = {**body, "instruction_ids": ["pay-9"]}
        with pytest.raises(ValueError, match="signature"):
            provider.verify_webhook({}, tampered)


class TestWechatAdapter:
    def test_missing_key_raises(self):
        with pytest.raises(ProviderNotConfiguredError, match="SKILLOS_WECHAT"):
            WeChatPayProvider(mch_id="", apiv3_key="")

    def test_v3_signed_headers(self):
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key", mch_cert_sn="sn-1")
        manifest = {"manifest_id": "pay-abc", "total_amount": 100.0, "payee": {"openid": "o-1"}}
        ref = provider.submit_manifest(manifest)
        assert ref.provider == "wechat"
        assert ref.status == "submitted"
        assert ref.external_ref == "pay-abc"

    def test_query_status_builds_headers(self):
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key")
        status = provider.query_status("wx-abc")
        assert status.status == "succeeded"
        assert "Authorization" in status.raw["headers"]
        assert "WECHATPAY2-SHA256-RSA2048" in status.raw["headers"]["Authorization"]

    def test_webhook_ok(self):
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key")
        receipt = provider.verify_webhook(
            {"wechatpay-serial": "sn-1"},
            {
                "event_type": "TRANSFER.TRANSFER_SUCCESS",
                "resource": {"instruction_ids": ["pay-1", "pay-2"]},
            },
        )
        assert receipt.instruction_ids == ["pay-1", "pay-2"]

    def test_webhook_missing_serial(self):
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key")
        with pytest.raises(ValueError, match="Wechatpay-Serial"):
            provider.verify_webhook({}, {"event_type": "TRANSFER.TRANSFER_SUCCESS", "resource": {}})
