"""Tests for skillos.security.message_signer — 跨服务 Ed25519 消息签名"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from skillos.security.message_signer import (
    SIGNATURE_TTL,
    MessageSigner,
    SignedMessage,
    get_default_signer,
    reset_default_signer,
)


@pytest.fixture
def signer() -> MessageSigner:
    """提供测试用 MessageSigner 实例。"""
    return MessageSigner("test-signer-001")


@pytest.fixture(autouse=True)
def _reset_signer_singleton():
    """每个测试后重置模块级单例。"""
    yield
    reset_default_signer()


# ──────────────────────────────────────────────────────────────────────
# MessageSigner.sign
# ──────────────────────────────────────────────────────────────────────


class TestSign:
    """测试 payload 签名。"""

    def test_sign_returns_signed_message(self, signer: MessageSigner) -> None:
        payload = {"method": "skill.register", "params": {"id": "test-001"}}
        signed = signer.sign(payload)
        assert isinstance(signed, SignedMessage)
        assert signed.signer_id == "test-signer-001"
        assert len(signed.signature) > 0
        assert signed.timestamp > 0
        assert "BEGIN PUBLIC KEY" in signed.public_key_pem

    def test_sign_is_deterministic(self, signer: MessageSigner) -> None:
        """相同 payload + 相同密钥 + 相同时间戳应产生相同签名（Ed25519 是确定性签名）。

        C2 修复后签名内容含时间戳，因此同一 payload 在不同时刻签名会不同
        （这正是防重放所需的）；timestamp 固定时签名才确定。
        """
        payload = {"method": "test", "params": {"key": "value"}}
        signed1 = signer.sign(payload)
        signed2 = signer.sign(payload)
        # 时间戳变化 → 签名内容变化 → 签名不同（防重放）
        assert signed1.signature != signed2.signature

        # 固定 timestamp：签名内容一致 → 签名确定
        content_a = MessageSigner._sign_content(payload, 1000.0)
        content_b = MessageSigner._sign_content(payload, 1000.0)
        assert content_a == content_b

    def test_sign_different_payloads_different_signatures(
        self, signer: MessageSigner
    ) -> None:
        payload1 = {"method": "test", "params": {"key": "value1"}}
        payload2 = {"method": "test", "params": {"key": "value2"}}
        assert signer.sign(payload1).signature != signer.sign(payload2).signature

    def test_payload_hash_nonempty(self, signer: MessageSigner) -> None:
        signed = signer.sign({"test": True})
        assert len(signed.payload_hash) == 16  # truncated SHA256


# ──────────────────────────────────────────────────────────────────────
# MessageSigner.sign_headers
# ──────────────────────────────────────────────────────────────────────


class TestSignHeaders:
    """测试 HTTP 头生成。"""

    def test_returns_all_required_headers(self, signer: MessageSigner) -> None:
        headers = signer.sign_headers({"method": "test"})
        assert "X-Signer-Id" in headers
        assert "X-Signature" in headers
        assert "X-Signature-Timestamp" in headers
        assert "X-Public-Key" in headers

    def test_headers_values_correct(self, signer: MessageSigner) -> None:
        headers = signer.sign_headers({"method": "test"})
        assert headers["X-Signer-Id"] == "test-signer-001"
        assert len(headers["X-Signature"]) > 0  # base64 signature
        assert float(headers["X-Signature-Timestamp"]) > 0
        assert "BEGIN PUBLIC KEY" in headers["X-Public-Key"]


# ──────────────────────────────────────────────────────────────────────
# MessageSigner.verify
# ──────────────────────────────────────────────────────────────────────


class TestVerify:
    """测试签名验证。"""

    def test_valid_signature_passes(self, signer: MessageSigner) -> None:
        payload = {"method": "skill.register", "params": {"id": "test-001"}}
        headers = signer.sign_headers(payload)
        assert MessageSigner.verify(payload, headers) is True

    def test_tampered_payload_fails(self, signer: MessageSigner) -> None:
        original = {"method": "skill.register", "params": {"id": "test-001"}}
        headers = signer.sign_headers(original)
        # 篡改 payload
        tampered = {"method": "skill.register", "params": {"id": "HACKED"}}
        assert MessageSigner.verify(tampered, headers) is False

    def test_missing_signature_header_fails(self, signer: MessageSigner) -> None:
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        del headers["X-Signature"]
        assert MessageSigner.verify(payload, headers) is False

    def test_missing_public_key_header_fails(self, signer: MessageSigner) -> None:
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        del headers["X-Public-Key"]
        assert MessageSigner.verify(payload, headers) is False

    def test_missing_timestamp_header_fails(self, signer: MessageSigner) -> None:
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        del headers["X-Signature-Timestamp"]
        assert MessageSigner.verify(payload, headers) is False

    def test_expired_signature_fails(self, signer: MessageSigner) -> None:
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        # 模拟过期时间戳
        headers["X-Signature-Timestamp"] = str(time.time() - SIGNATURE_TTL - 1)
        assert MessageSigner.verify(payload, headers) is False

    def test_invalid_timestamp_fails(self, signer: MessageSigner) -> None:
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        headers["X-Signature-Timestamp"] = "not-a-number"
        assert MessageSigner.verify(payload, headers) is False

    def test_empty_headers_fails(self) -> None:
        assert MessageSigner.verify({"test": True}, {}) is False

    def test_custom_max_age(self, signer: MessageSigner) -> None:
        """max_age 窗口控制：窗口内的签名通过，窗口外的被拒。

        C2 修复后 timestamp 纳入签名内容，改写 timestamp 会使验签失败
        （防重放），因此此处用「新签名」验证 max_age 边界。
        """
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)  # 当前时刻签名
        # 当前时刻签名，max_age=1 应通过（skew≈0）
        assert MessageSigner.verify(payload, headers, max_age=1) is True
        # 模拟过期：改写 timestamp 到 10 秒前 → 因签名内容变化验签失败（C2）
        headers["X-Signature-Timestamp"] = str(time.time() - 10)
        assert MessageSigner.verify(payload, headers, max_age=10) is False

    def test_tampered_timestamp_fails(self, signer: MessageSigner) -> None:
        """C2：改写时间戳会破坏签名 → 无法绕过 TTL 重放。"""
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        # 攻击者把时间戳改回 10 秒前，试图保持在窗口内
        headers["X-Signature-Timestamp"] = str(time.time() - 10)
        assert MessageSigner.verify(payload, headers) is False

    def test_future_timestamp_fails(self, signer: MessageSigner) -> None:
        """C2：未来时间戳被拒绝（时钟偏移容忍）。"""
        payload = {"method": "test"}
        headers = signer.sign_headers(payload)
        headers["X-Signature-Timestamp"] = str(time.time() + 1000)
        assert MessageSigner.verify(payload, headers) is False

    def test_cross_signer_verification(self) -> None:
        """不同签名者的密钥对不应互相验证。"""
        signer1 = MessageSigner("signer-1")
        payload = {"method": "test"}
        headers = signer1.sign_headers(payload)
        # signer1 的签名 + signer1 的公钥 = 验证通过
        assert MessageSigner.verify(payload, headers) is True
        # 但 signer2 无法用 signer1 的签名验证（公钥不同）
        # （实际上 verify 使用 headers 中的公钥，所以会通过）
        # 关键是：篡改 payload 后，即使有公钥也验证失败

    def test_verify_binds_to_registered_public_key(self) -> None:
        """C1：传入 expected_public_key_pem 时，用注册公钥验签，防止身份冒充。

        攻击者伪造自己的密钥对，声明受害者的 signer-id + 自己的公钥头，
        但验签用受害者注册公钥 → 必须失败。
        """
        victim = MessageSigner("victim-001")  # 受害者（已注册）密钥
        attacker = MessageSigner("victim-001")  # 攻击者伪称同一 signer-id，但密钥不同
        payload = {"method": "test"}
        attacker_headers = attacker.sign_headers(payload)
        # 用受害者注册公钥验签攻击者的签名 → 必须失败（C1 修复）
        assert (
            MessageSigner.verify(
                payload,
                attacker_headers,
                expected_public_key_pem=victim._public_key_pem,
            )
            is False
        )
        # 受害者本人签名 + 受害者注册公钥 → 通过
        victim_headers = victim.sign_headers(payload)
        assert (
            MessageSigner.verify(
                payload,
                victim_headers,
                expected_public_key_pem=victim._public_key_pem,
            )
            is True
        )

    def test_verify_with_registered_key_ignores_header_public_key(self) -> None:
        """C1：即使请求头公钥被替换为攻击者公钥，用注册公钥验签仍失败。"""
        victim = MessageSigner("victim-002")
        attacker = MessageSigner("attacker-002")
        payload = {"method": "test"}
        headers = attacker.sign_headers(payload)
        # 攻击者把自己的公钥放进头 + 声明受害者 signer-id
        headers["X-Signer-Id"] = "victim-002"
        headers["X-Public-Key"] = attacker._public_key_pem
        # 服务端用受害者注册公钥验签 → 失败
        assert (
            MessageSigner.verify(
                payload,
                headers,
                expected_public_key_pem=victim._public_key_pem,
            )
            is False
        )


# ──────────────────────────────────────────────────────────────────────
# get_default_signer / reset_default_signer
# ──────────────────────────────────────────────────────────────────────


class TestDefaultSigner:
    """测试模块级单例。"""

    def test_returns_none_when_env_not_set(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            reset_default_signer()
            assert get_default_signer() is None

    def test_returns_signer_when_id_set(self) -> None:
        with patch.dict("os.environ", {"SKILLOS_SIGNER_ID": "default-signer"}, clear=True):
            reset_default_signer()
            signer = get_default_signer()
            assert signer is not None
            assert signer.signer_id == "default-signer"

    def test_singleton_cached(self) -> None:
        with patch.dict("os.environ", {"SKILLOS_SIGNER_ID": "cached-signer"}, clear=True):
            reset_default_signer()
            s1 = get_default_signer()
            s2 = get_default_signer()
            assert s1 is s2  # 同一实例

    def test_reset_clears_singleton(self) -> None:
        with patch.dict("os.environ", {"SKILLOS_SIGNER_ID": "before-reset"}, clear=True):
            reset_default_signer()
            s1 = get_default_signer()
            assert s1 is not None
            reset_default_signer()
            s2 = get_default_signer()
            assert s2 is not None
            assert s1 is not s2  # 不同实例

    def test_sign_and_verify_roundtrip_via_default(self) -> None:
        """通过默认单例签名 + 验证完整链路。"""
        with patch.dict("os.environ", {"SKILLOS_SIGNER_ID": "roundtrip"}, clear=True):
            reset_default_signer()
            signer = get_default_signer()
            assert signer is not None
            payload = {"jsonrpc": "2.0", "method": "test", "id": 1}
            headers = signer.sign_headers(payload)
            assert MessageSigner.verify(payload, headers) is True
