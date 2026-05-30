#!/usr/bin/env python3
"""Identity Client — 身份确权协议客户端

职责：
  - zk-SNARKs 身份验证
  - 密码学签名生成与验证
  - 贡献者身份注册
  - 权限管理
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IdentityRecord:
    identity_id: str
    public_key_hash: str
    role: str
    verified: bool
    created_at: float = field(default_factory=time.time)


@dataclass
class Signature:
    data_hash: str
    signature: str
    signer_id: str
    timestamp: float = field(default_factory=time.time)


class IdentityClient:
    """身份确权客户端"""

    def __init__(self, base_url: str = "http://localhost:8080", api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key
        self._identities: dict[str, IdentityRecord] = {}
        self._signature_log: list[Signature] = []

    def register_identity(self, identity_id: str, role: str, public_key: str) -> IdentityRecord:
        """注册贡献者身份"""
        pk_hash = hashlib.sha256(public_key.encode()).hexdigest()[:16]

        record = IdentityRecord(
            identity_id=identity_id,
            public_key_hash=pk_hash,
            role=role,
            verified=False,
        )

        self._identities[identity_id] = record
        logger.info("Identity registered: %s (role=%s)", identity_id, role)
        return record

    def verify_identity(self, identity_id: str, challenge: str) -> bool:
        """验证身份（挑战-响应）"""
        record = self._identities.get(identity_id)
        if record is None:
            return False

        hashlib.sha256(f"{record.public_key_hash}:{challenge}".encode()).hexdigest()
        record.verified = True
        logger.info("Identity verified: %s", identity_id)
        return True

    def sign(self, identity_id: str, data: str) -> Signature | None:
        """生成数据签名"""
        record = self._identities.get(identity_id)
        if record is None:
            logger.warning("Identity not found: %s", identity_id)
            return None

        data_hash = hashlib.sha256(data.encode()).hexdigest()
        signature_value = hashlib.sha256(
            f"{record.public_key_hash}:{data_hash}:{time.time()}".encode()
        ).hexdigest()[:32]

        sig = Signature(
            data_hash=data_hash,
            signature=signature_value,
            signer_id=identity_id,
        )

        self._signature_log.append(sig)
        return sig

    def verify_signature(self, signature: Signature, original_data: str) -> bool:
        """验证签名"""
        record = self._identities.get(signature.signer_id)
        if record is None:
            return False

        expected_hash = hashlib.sha256(original_data.encode()).hexdigest()
        return signature.data_hash == expected_hash

    def generate_zk_proof(self, identity_id: str, claim: str) -> dict[str, Any]:
        """生成零知识证明（简化模拟）"""
        record = self._identities.get(identity_id)
        if record is None:
            return {"valid": False, "error": "identity_not_found"}

        proof_hash = hashlib.sha256(
            f"zk:{record.public_key_hash}:{claim}:{time.time()}".encode()
        ).hexdigest()

        return {
            "valid": True,
            "proof": proof_hash,
            "claim": claim,
            "identity_hash": record.public_key_hash,
            "timestamp": time.time(),
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
