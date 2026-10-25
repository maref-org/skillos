#!/usr/bin/env python3
"""Identity Client — 身份确权协议客户端

职责：
  - Ed25519 密码学身份验证
  - 密码学签名生成与验证
  - 贡献者身份注册
  - 权限管理
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from skillos.audit import AuditEventType, log_audit

logger = logging.getLogger(__name__)


@dataclass
class IdentityRecord:
    identity_id: str
    public_key_pem: str
    role: str
    verified: bool
    created_at: float = field(default_factory=time.time)


@dataclass
class Signature:
    data_hash: str
    signature: str  # base64-encoded Ed25519 signature
    signer_id: str
    timestamp: float = field(default_factory=time.time)


class IdentityClient:
    """身份确权客户端 — 基于 Ed25519 真正密码学签名"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        # 强制 HTTPS：生产环境禁止 HTTP
        raw_url = base_url or os.getenv("SKILLOS_IDENTITY_URL", "https://localhost:8080")
        self.base_url = self._enforce_https(raw_url)  # type: ignore[arg-type]
        # API Key 从环境变量读取，禁止明文存储
        self._api_key = api_key or os.getenv("SKILLOS_API_KEY")
        self._identities: dict[str, IdentityRecord] = {}
        self._signature_log: list[Signature] = []
        # 内存中的私钥缓存（仅用于当前进程签名，不持久化）
        self._private_keys: dict[str, Ed25519PrivateKey] = {}

    @staticmethod
    def _enforce_https(url: str) -> str:
        """强制使用 HTTPS，禁止明文 HTTP 传输"""
        if url.startswith("http://"):
            # 开发环境可通过环境变量允许 HTTP
            if os.getenv("SKILLOS_INSECURE", "0") == "1":
                logger.warning("Insecure HTTP enabled via SKILLOS_INSECURE=1")
                return url
            raise ValueError(
                "HTTP is not allowed in production. Use HTTPS or set SKILLOS_INSECURE=1 for development only."
            )
        if not url.startswith("https://"):
            return f"https://{url}"
        return url

    def register_identity(
        self,
        identity_id: str,
        role: str,
        public_key_pem: str | None = None,
    ) -> IdentityRecord:
        """注册贡献者身份

        Args:
            identity_id: 唯一身份标识
            role: 角色（如 developer, reviewer, admin）
            public_key_pem: Ed25519 公钥 PEM 字符串（可选，未提供则生成新密钥对）

        Returns:
            IdentityRecord: 注册记录
        """
        if not identity_id or not isinstance(identity_id, str):
            raise ValueError("identity_id must be a non-empty string")
        if not role or not isinstance(role, str):
            raise ValueError("role must be a non-empty string")

        if public_key_pem:
            # 验证 PEM 格式正确性
            try:
                self._load_public_key(public_key_pem)
            except Exception as exc:
                raise ValueError(f"Invalid Ed25519 public key PEM: {exc}") from exc
        else:
            # 生成新的 Ed25519 密钥对
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("utf-8")
            self._private_keys[identity_id] = private_key
            logger.info("Generated new Ed25519 key pair for identity: %s", identity_id)

        if public_key_pem is None:
            raise ValueError("public_key_pem is required")

        record = IdentityRecord(
            identity_id=identity_id,
            public_key_pem=public_key_pem,
            role=role,
            verified=False,
        )

        self._identities[identity_id] = record
        logger.info("Identity registered: %s (role=%s)", identity_id, role)
        log_audit(
            AuditEventType.IDENTITY_REGISTERED,
            identity_id,
            identity_id,
            f"Register identity (role={role})",
            {"role": role, "verified": False},
        )
        return record

    def verify_identity(self, identity_id: str, challenge: str, challenge_signature: str) -> bool:
        """验证身份（挑战-响应）

        Args:
            identity_id: 身份标识
            challenge: 服务端生成的随机挑战字符串
            challenge_signature: 客户端使用私钥对 challenge 的签名（base64）

        Returns:
            bool: 验证是否成功
        """
        record = self._identities.get(identity_id)
        if record is None:
            logger.warning("Identity not found for verification: %s", identity_id)
            log_audit(
                AuditEventType.AUTH_FAILURE,
                identity_id,
                identity_id,
                "Identity verification failed (identity not found)",
                {"reason": "identity_not_found"},
            )
            return False

        if not challenge or not isinstance(challenge, str):
            logger.warning("Invalid challenge for identity: %s", identity_id)
            log_audit(
                AuditEventType.AUTH_FAILURE,
                identity_id,
                identity_id,
                "Identity verification failed (invalid challenge)",
                {"reason": "invalid_challenge"},
            )
            return False

        try:
            public_key = self._load_public_key(record.public_key_pem)
            signature_bytes = self._b64decode(challenge_signature)
            public_key.verify(signature_bytes, challenge.encode("utf-8"))
            record.verified = True
            logger.info("Identity verified: %s", identity_id)
            log_audit(
                AuditEventType.IDENTITY_VERIFIED,
                identity_id,
                identity_id,
                "Identity verified (challenge-response)",
                {"role": record.role},
            )
            return True
        except InvalidSignature:
            logger.warning("Invalid challenge signature for identity: %s", identity_id)
            log_audit(
                AuditEventType.AUTH_FAILURE,
                identity_id,
                identity_id,
                "Identity verification failed (invalid signature)",
                {"reason": "invalid_signature"},
            )
            return False
        except Exception as exc:
            logger.error("Verification error for identity %s: %s", identity_id, exc)
            log_audit(
                AuditEventType.AUTH_FAILURE,
                identity_id,
                identity_id,
                "Identity verification failed (exception)",
                {"reason": "verification_error", "error": str(exc)},
            )
            return False

    def sign(self, identity_id: str, data: str) -> Signature | None:
        """生成数据签名（Ed25519 真正密码学签名）

        Args:
            identity_id: 签名者身份标识
            data: 待签名数据

        Returns:
            Signature | None: 签名对象，身份不存在或无私钥时返回 None
        """
        record = self._identities.get(identity_id)
        if record is None:
            logger.warning("Identity not found: %s", identity_id)
            return None

        if not data or not isinstance(data, str):
            logger.warning("Invalid data to sign for identity: %s", identity_id)
            return None

        private_key = self._private_keys.get(identity_id)
        if private_key is None:
            logger.error(
                "No private key available for identity: %s. Only identities created by this client can sign.",
                identity_id,
            )
            return None

        data_hash = hashlib.sha256(data.encode("utf-8")).hexdigest()
        signature_bytes = private_key.sign(data.encode("utf-8"))
        signature_value = self._b64encode(signature_bytes)

        sig = Signature(
            data_hash=data_hash,
            signature=signature_value,
            signer_id=identity_id,
        )

        self._signature_log.append(sig)
        logger.info("Data signed by identity: %s", identity_id)
        return sig

    def verify_signature(self, signature: Signature, original_data: str) -> bool:
        """验证 Ed25519 签名

        Args:
            signature: 签名对象
            original_data: 原始数据

        Returns:
            bool: 签名是否有效
        """
        record = self._identities.get(signature.signer_id)
        if record is None:
            logger.warning("Identity not found for signature verification: %s", signature.signer_id)
            log_audit(
                AuditEventType.IDENTITY_SIGN,
                signature.signer_id,
                signature.data_hash,
                "Signature verification failed (identity not found)",
                {"valid": False, "reason": "identity_not_found"},
            )
            return False

        try:
            public_key = self._load_public_key(record.public_key_pem)
            signature_bytes = self._b64decode(signature.signature)
            public_key.verify(signature_bytes, original_data.encode("utf-8"))

            # 同时验证数据哈希一致性
            expected_hash = hashlib.sha256(original_data.encode("utf-8")).hexdigest()
            if signature.data_hash != expected_hash:
                logger.warning("Data hash mismatch for signature by identity: %s", signature.signer_id)
                log_audit(
                    AuditEventType.IDENTITY_SIGN,
                    signature.signer_id,
                    signature.data_hash,
                    "Signature verification failed (hash mismatch)",
                    {"valid": False, "reason": "hash_mismatch"},
                )
                return False

            logger.info("Signature verified for identity: %s", signature.signer_id)
            log_audit(
                AuditEventType.IDENTITY_SIGN,
                signature.signer_id,
                signature.data_hash,
                "Signature verified (Ed25519)",
                {"valid": True},
            )
            return True
        except InvalidSignature:
            logger.warning("Invalid signature for identity: %s", signature.signer_id)
            log_audit(
                AuditEventType.IDENTITY_SIGN,
                signature.signer_id,
                signature.data_hash,
                "Signature verification failed (invalid signature)",
                {"valid": False, "reason": "invalid_signature"},
            )
            return False
        except Exception as exc:
            logger.error("Signature verification error for %s: %s", signature.signer_id, exc)
            log_audit(
                AuditEventType.IDENTITY_SIGN,
                signature.signer_id,
                signature.data_hash,
                "Signature verification failed (exception)",
                {"valid": False, "reason": "verification_error", "error": str(exc)},
            )
            return False

    def generate_challenge(self, identity_id: str) -> dict[str, Any]:
        """生成挑战-响应验证的挑战值

        Args:
            identity_id: 待验证的身份标识

        Returns:
            dict: 包含 challenge 和过期时间的字典
        """
        import secrets

        record = self._identities.get(identity_id)
        if record is None:
            return {"valid": False, "error": "identity_not_found"}

        challenge = secrets.token_urlsafe(32)
        expires_at = time.time() + 300  # 5 分钟过期

        return {
            "valid": True,
            "identity_id": identity_id,
            "challenge": challenge,
            "expires_at": expires_at,
        }

    def generate_zk_proof(self, identity_id: str, claim: str) -> dict[str, Any]:
        """生成零知识证明（简化模拟 — 当前版本为概念实现）

        警告: 当前实现为密码学承诺模拟，非真正的 zk-SNARKs。
        生产环境应集成 circom/snarkjs 或类似方案。
        """
        record = self._identities.get(identity_id)
        if record is None:
            return {"valid": False, "error": "identity_not_found"}

        # 使用 HMAC-SHA256 作为密码学承诺（比简单哈希更安全）
        import hmac

        commitment = hmac.new(
            record.public_key_pem.encode("utf-8"),
            f"zk:{claim}:{time.time()}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "valid": True,
            "proof": commitment,
            "claim": claim,
            "identity_id": identity_id,
            "timestamp": time.time(),
            "note": "simulated_zk_proof",
        }

    def get_identity(self, identity_id: str) -> IdentityRecord | None:
        return self._identities.get(identity_id)

    def list_identities(self, role: str | None = None) -> list[IdentityRecord]:
        identities = list(self._identities.values())
        if role:
            identities = [i for i in identities if i.role == role]
        return identities

    def get_signature_log(self, identity_id: str | None = None) -> list[Signature]:
        if identity_id:
            return [s for s in self._signature_log if s.signer_id == identity_id]
        return list(self._signature_log)

    @staticmethod
    def _load_public_key(pem: str) -> Ed25519PublicKey:
        return serialization.load_pem_public_key(pem.encode("utf-8"))  # type: ignore[return-value]

    @staticmethod
    def _b64encode(data: bytes) -> str:
        import base64

        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _b64decode(data: str) -> bytes:
        import base64

        return base64.b64decode(data)
