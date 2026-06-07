#!/usr/bin/env python3
"""ZK Verifier — 零知识验证（模拟实现）

使用 HMAC-SHA256 模拟零知识承诺验证。
生产环境应替换为真实 zk-SNARKs 验证器。
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone

from skillos.negmarket.models import ZKProof

logger = logging.getLogger(__name__)


class ZKVerifier:
    """零知识验证器（模拟）

    用 HMAC-SHA256(contributor_secret, data) 模拟：
      - 贡献者可证明样本所有权，不泄露样本内容
      - 验证者仅校验 HMAC 是否匹配已知贡献者
    """

    _SIMULATED_SECRET = b"negmarket-zk-sim-v0.4.0"

    def prove(self, data: str, contributor_id: str) -> ZKProof:
        sample_hash = hashlib.sha256(data.encode()).hexdigest()
        proof_value = hmac.new(
            self._SIMULATED_SECRET,
            f"{contributor_id}:{sample_hash}".encode(),
            hashlib.sha256,
        ).hexdigest()
        logger.info("ZK proof generated for contributor %s", contributor_id)
        return ZKProof(
            sample_id=sample_hash[:16],
            proof_value=proof_value,
            verified=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def verify(self, proof: ZKProof, contributor_id: str, data_hash: str) -> bool:
        expected = hmac.new(
            self._SIMULATED_SECRET,
            f"{contributor_id}:{data_hash}".encode(),
            hashlib.sha256,
        ).hexdigest()
        result = hmac.compare_digest(proof.proof_value, expected)
        proof.verified = result
        logger.info("ZK proof verification: %s for contributor %s", "PASS" if result else "FAIL", contributor_id)
        return result
