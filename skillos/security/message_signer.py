#!/usr/bin/env python3
"""Message Signer — 跨服务请求 Ed25519 签名层

职责：
  - 对 JSON-RPC payload 进行 Ed25519 签名
  - 生成签名头（X-Signer-Id / X-Signature / X-Timestamp / X-Public-Key）
  - 提供服务端验证方法

设计意图：
  - 复用 IdentityClient 的 Ed25519 能力，但独立于 IdentityClient 运行
  - 协议客户端（registry / matcher / settlement）通过 _auth_headers() 接入
  - 签名覆盖 canonical JSON，防止 payload 篡改
  - 时间戳防重放（服务端可校验时间窗口）

使用示例::

    from skillos.security.message_signer import get_default_signer

    signer = get_default_signer()
    headers = signer.sign_headers(payload)
    # headers → {"X-Signer-Id": "...", "X-Signature": "...", ...}
    # 合并到 requests.post(headers={**auth_headers, **sign_headers})
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = logging.getLogger(__name__)

# 签名有效期窗口（秒）— 超过此时间的签名被拒绝
SIGNATURE_TTL = 300.0


@dataclass
class SignedMessage:
    """已签名的消息元数据。"""

    signer_id: str
    signature: str  # base64-encoded Ed25519 signature
    timestamp: float
    public_key_pem: str
    payload_hash: str = ""  # SHA256 of canonical payload（调试用）


class MessageSigner:
    """Ed25519 消息签名器 — 跨服务请求签名。

    生命周期：
      - 进程级单例通过 ``get_default_signer()`` 获取
      - 密钥对从环境变量加载或自动生成
      - 自动生成的密钥对会记录 warning（跨重启验证不可用）
    """

    def __init__(
        self,
        signer_id: str,
        private_key: Ed25519PrivateKey | None = None,
    ) -> None:
        self.signer_id = signer_id
        self._private_key = private_key or Ed25519PrivateKey.generate()
        self._public_key: Ed25519PublicKey = self._private_key.public_key()
        self._public_key_pem: str = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        if private_key is None:
            logger.warning(
                "MessageSigner for '%s' using auto-generated key pair. "
                "Set SKILLOS_SIGNER_PRIVATE_KEY for cross-restart verification.",
                signer_id,
            )

    def sign(self, payload: dict[str, Any]) -> SignedMessage:
        """对 payload 进行 Ed25519 签名。

        签名内容为 ``canonical(payload) + timestamp`` —— 时间戳纳入签名，
        防止攻击者改写时间戳绕过 TTL 重放（C2 修复）。

        Args:
            payload: 待签名的 JSON-serializable 字典（通常是 JSON-RPC 2.0 payload）

        Returns:
            SignedMessage: 签名元数据
        """
        timestamp = time.time()
        canonical = self._sign_content(payload, timestamp)
        signature_bytes = self._private_key.sign(canonical.encode("utf-8"))

        return SignedMessage(
            signer_id=self.signer_id,
            signature=base64.b64encode(signature_bytes).decode("ascii"),
            timestamp=timestamp,
            public_key_pem=self._public_key_pem,
            payload_hash=hashlib.sha256(self._canonicalize(payload).encode("utf-8")).hexdigest()[:16],
        )

    def sign_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """对 payload 签名并返回 HTTP 头字典。

        将以下头添加到请求中：
          - ``X-Signer-Id``: 签名者身份标识
          - ``X-Signature``: base64 编码的 Ed25519 签名
          - ``X-Signature-Timestamp``: 签名时间戳（Unix epoch）
          - ``X-Public-Key``: 签名者公钥 PEM（服务端验证用）

        Args:
            payload: 待签名的 payload

        Returns:
            dict: HTTP 头字典，合并到 ``requests.post(headers=...)``
        """
        signed = self.sign(payload)
        return {
            "X-Signer-Id": signed.signer_id,
            "X-Signature": signed.signature,
            "X-Signature-Timestamp": str(signed.timestamp),
            "X-Public-Key": signed.public_key_pem,
        }

    def sign_headers_http(self, payload: dict[str, Any]) -> dict[str, str]:
        """对 payload 签名并返回 HTTP 头字典（header 友好编码）。

        ``X-Public-Key`` 用 base64url（无换行）编码，适用于真实 HTTP 传输
        （HTTP 头不允许含换行符）。服务端 ``verify`` 自动识别并解码。

        Args:
            payload: 待签名的 payload

        Returns:
            dict: HTTP 头字典，合并到 ``httpx.post(headers=...)``
        """
        headers = self.sign_headers(payload)
        headers["X-Public-Key"] = base64.urlsafe_b64encode(
            self._public_key_pem.encode("utf-8")
        ).decode("ascii")
        return headers

    @staticmethod
    def verify(
        payload: dict[str, Any],
        headers: dict[str, str],
        *,
        max_age: float = SIGNATURE_TTL,
        expected_public_key_pem: str | None = None,
    ) -> bool:
        """验证请求签名（服务端使用）。

        Args:
            payload: 接收到的 payload（已解析的 dict）
            headers: 请求头（包含 X-Signature 等）
            max_age: 签名最大有效期（秒），默认 300
            expected_public_key_pem: 签名者注册公钥（可选）。

                传入时用该公钥验签（不信任请求头里的公钥，C1 修复），
                从而保证签名者身份与已注册公钥绑定，防止身份冒充。

        Returns:
            bool: 签名是否有效
        """
        signature_b64 = headers.get("X-Signature", "")
        timestamp_str = headers.get("X-Signature-Timestamp", "")
        public_key_pem = headers.get("X-Public-Key", "")

        if not signature_b64 or not timestamp_str or not public_key_pem:
            # HTTP 头名大小写不敏感（如 x-signature）；做一次小写兜底查找
            lowered = {str(k).lower(): v for k, v in headers.items()}
            signature_b64 = lowered.get("x-signature", "")
            timestamp_str = lowered.get("x-signature-timestamp", "")
            public_key_pem = lowered.get("x-public-key", "")

        if not signature_b64 or not timestamp_str or not public_key_pem:
            logger.warning("Missing signature headers for verification")
            return False

        # 时间窗口校验（防重放）：拒绝过期与未来时间戳
        try:
            timestamp = float(timestamp_str)
        except ValueError:
            logger.warning("Invalid signature timestamp: %s", timestamp_str)
            return False

        skew = time.time() - timestamp
        if skew > max_age or skew < -max_age:
            logger.warning("Signature outside time window (age=%.1fs, max=%.1fs)", skew, max_age)
            return False

        # 选择验签公钥：优先用注册公钥（C1），否则回退 header 公钥（协议客户端兼容）
        if expected_public_key_pem is not None:
            key_pem = expected_public_key_pem
        else:
            key_pem = public_key_pem

        # 加载公钥（支持 PEM 或 base64url 编码 PEM —— header 友好传输）
        try:
            if "-----BEGIN" in key_pem:
                public_key = serialization.load_pem_public_key(key_pem.encode("utf-8"))
            else:
                # base64url 编码的 PEM
                pem_bytes = base64.urlsafe_b64decode(key_pem.encode("ascii"))
                public_key = serialization.load_pem_public_key(pem_bytes)
            if not isinstance(public_key, Ed25519PublicKey):
                logger.warning("Public key is not Ed25519")
                return False
        except Exception as exc:
            logger.warning("Failed to load public key: %s", exc)
            return False

        # 验证签名（签名内容 = canonical(payload) + timestamp，timestamp 被改写即失败）
        canonical = MessageSigner._sign_content(payload, timestamp)
        try:
            signature_bytes = base64.b64decode(signature_b64)
            public_key.verify(signature_bytes, canonical.encode("utf-8"))
            return True
        except Exception as exc:
            logger.warning("Signature verification failed: %s", exc)
            return False

    @staticmethod
    def _canonicalize(payload: dict[str, Any]) -> str:
        """将 payload 序列化为 canonical JSON（确定性排序）。"""
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _sign_content(payload: dict[str, Any], timestamp: float) -> str:
        """构造签名内容：canonical payload + 时间戳（C2 防重放）。"""
        return f"{MessageSigner._canonicalize(payload)}\n{timestamp}"


# ──────────────────────────────────────────────────────────────────────
# 模块级单例
# ──────────────────────────────────────────────────────────────────────

_default_signer: MessageSigner | None = None


def get_default_signer() -> MessageSigner | None:
    """返回进程级 MessageSigner 单例。

    从环境变量加载配置：
      - ``SKILLOS_SIGNER_ID``: 签名者 ID（必需，未设置则返回 None）
      - ``SKILLOS_SIGNER_PRIVATE_KEY``: Ed25519 私钥 PEM（可选，未设置则自动生成）

    Returns:
        MessageSigner | None: 若 ``SKILLOS_SIGNER_ID`` 未设置则返回 None（签名禁用）
    """
    global _default_signer
    if _default_signer is not None:
        return _default_signer

    signer_id = os.getenv("SKILLOS_SIGNER_ID")
    if not signer_id:
        # 签名未配置 — 协议客户端应优雅降级为仅 Bearer token
        return None

    private_key_pem = os.getenv("SKILLOS_SIGNER_PRIVATE_KEY")
    private_key: Ed25519PrivateKey | None = None
    if private_key_pem:
        try:
            loaded = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
            )
            if isinstance(loaded, Ed25519PrivateKey):
                private_key = loaded
            else:
                logger.warning("SKILLOS_SIGNER_PRIVATE_KEY is not Ed25519, generating new key")
        except Exception as exc:
            logger.warning("Failed to load SKILLOS_SIGNER_PRIVATE_KEY: %s", exc)

    _default_signer = MessageSigner(signer_id, private_key)
    return _default_signer


def reset_default_signer() -> None:
    """重置单例（仅供测试使用）。"""
    global _default_signer
    _default_signer = None
