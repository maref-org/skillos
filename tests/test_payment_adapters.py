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

    def test_webhook_fail_closed_without_pubkey(self):
        """C6：无支付宝公钥时 webhook 校验 fail-closed（不降级字段校验）。"""
        provider = AlipayProvider(
            app_id="app-test",
            private_key_pem="dummy-private-key",
            gateway="https://sandbox",
        )
        with pytest.raises(ValueError, match="SKILLOS_ALIPAY_PUBLIC_KEY"):
            provider.verify_webhook(
                {},
                {
                    "app_id": "app-test",
                    "notify_type": "fund_trans_order_status",
                    "status": "SUCCESS",
                    "instruction_ids": ["pay-1"],
                },
            )

    def test_webhook_bad_app_id(self):
        """配置公钥后仍校验 app_id（签名通过后二次校验）。"""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        from skillos.market.payments.alipay import _build_sign_content

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
        body = {
            "app_id": "other",
            "notify_type": "fund_trans_order_status",
            "instruction_ids": ["pay-1"],
        }
        content = _build_sign_content(body)
        sig = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        body["sign"] = __import__("base64").b64encode(sig).decode("utf-8")
        with pytest.raises(ValueError, match="app_id mismatch"):
            provider.verify_webhook({}, body)


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


class TestWechatRsaSignature:
    """M7-P1.3 — 微信 v3 真实商户证书 RSA-SHA256 签名（可选配置，无私钥保留 HMAC）。"""

    def _provider_with_private_key(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = (
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            .decode("utf-8")
        )
        provider = WeChatPayProvider(
            mch_id="mch-1",
            apiv3_key="v3-key",
            mch_cert_sn="sn-1",
            private_key_pem=pem,
        )
        return key, provider

    def test_signed_headers_use_rsa_sha256_when_private_key_set(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        key, provider = self._provider_with_private_key()
        headers = provider._signed_headers("POST", "/v3/x", {"a": 1})
        auth = headers["Authorization"]
        sig = auth.split('signature="')[1].split('"')[0]
        assert "WECHATPAY2-SHA256-RSA2048" in auth
        content = (
            "POST\n/v3/x\n%s\n%s\n%s\n"
            % (
                auth.split('timestamp="')[1].split('"')[0],
                auth.split('nonce_str="')[1].split('"')[0],
                '{"a":1}',
            )
        )
        key.public_key().verify(
            __import__("base64").b64decode(sig),
            content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

    def test_hmac_used_when_no_private_key(self):
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key")
        headers = provider._signed_headers("POST", "/v3/x", {"a": 1})
        sig = headers["Authorization"].split('signature="')[1].split('"')[0]
        # HMAC-SHA256 输出为 64 位 hex，RSA 签名为 base64（含 + / = 字符）
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)


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

    def _provider_with_platform_key(self):
        """构造配置了微信平台公钥的 provider（用于 v3 回调验签）。"""
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
        provider = WeChatPayProvider(
            mch_id="mch-1",
            apiv3_key="v3-key",
            mch_cert_sn="sn-1",
        )
        provider.platform_public_key_pem = pub_pem
        return key, provider

    def test_webhook_fail_closed_without_platform_key(self):
        """C5：无微信平台公钥时 webhook 校验 fail-closed（不靠 header 存在）。"""
        provider = WeChatPayProvider(mch_id="mch-1", apiv3_key="v3-key")
        with pytest.raises(ValueError, match="PLATFORM_PUBLIC_KEY"):
            provider.verify_webhook(
                {"wechatpay-serial": "sn-1"},
                {
                    "event_type": "TRANSFER.TRANSFER_SUCCESS",
                    "resource": {"instruction_ids": ["pay-1", "pay-2"]},
                },
            )

    def test_webhook_ok_with_valid_signature(self):
        """C5：配置平台公钥后，v3 签名有效才放行。"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        key, provider = self._provider_with_platform_key()
        body = {
            "event_type": "TRANSFER.TRANSFER_SUCCESS",
            "resource": {"instruction_ids": ["pay-1", "pay-2"], "out_bill_no": "wx-real-1"},
        }
        timestamp = "1785599999"
        nonce = "abc123"
        raw_body = __import__("json").dumps(body, ensure_ascii=False, separators=(",", ":"))
        content = f"{timestamp}\n{nonce}\n{raw_body}\n"
        sig = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        headers = {
            "wechatpay-serial": "sn-1",
            "wechatpay-timestamp": timestamp,
            "wechatpay-nonce": nonce,
            "wechatpay-signature": __import__("base64").b64encode(sig).decode("utf-8"),
        }
        receipt = provider.verify_webhook(headers, body)
        assert receipt.instruction_ids == ["pay-1", "pay-2"]
        assert receipt.external_ref == "wx-real-1"

    def test_webhook_rejects_tampered_body(self):
        """C5：篡改 body 后 v3 签名校验失败。"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        key, provider = self._provider_with_platform_key()
        body = {
            "event_type": "TRANSFER.TRANSFER_SUCCESS",
            "resource": {"instruction_ids": ["pay-1", "pay-2"]},
        }
        timestamp = "1785599999"
        nonce = "abc123"
        raw_body = __import__("json").dumps(body, ensure_ascii=False, separators=(",", ":"))
        content = f"{timestamp}\n{nonce}\n{raw_body}\n"
        sig = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        headers = {
            "wechatpay-serial": "sn-1",
            "wechatpay-timestamp": timestamp,
            "wechatpay-nonce": nonce,
            "wechatpay-signature": __import__("base64").b64encode(sig).decode("utf-8"),
        }
        tampered = {**body, "resource": {"instruction_ids": ["pay-9"]}}
        with pytest.raises(ValueError, match="signature"):
            provider.verify_webhook(headers, tampered)

    def test_webhook_uses_raw_body_when_provided(self):
        """C5：传入 raw_body 时对原始字节验签（微信 v3 规范），而非重序列化。"""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        key, provider = self._provider_with_platform_key()
        # 原始 body 带空格与不同 key 顺序（重序列化会改变字节）
        raw_body = (
            '{"resource": {"instruction_ids": ["pay-1"], "out_bill_no": "wx-1"}, '
            '"event_type": "TRANSFER.TRANSFER_SUCCESS"}'
        )
        body = {
            "event_type": "TRANSFER.TRANSFER_SUCCESS",
            "resource": {"instruction_ids": ["pay-1"], "out_bill_no": "wx-1"},
        }
        timestamp = "1785599999"
        nonce = "xyz"
        content = f"{timestamp}\n{nonce}\n{raw_body}\n"
        sig = key.sign(content.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        headers = {
            "wechatpay-serial": "sn-1",
            "wechatpay-timestamp": timestamp,
            "wechatpay-nonce": nonce,
            "wechatpay-signature": __import__("base64").b64encode(sig).decode("utf-8"),
        }
        # 若用重序列化验签（非 raw），此签名必失败；传 raw_body 后应通过
        receipt = provider.verify_webhook(headers, body, raw_body=raw_body)
        assert receipt.instruction_ids == ["pay-1"]
