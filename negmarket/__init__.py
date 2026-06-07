#!/usr/bin/env python3
"""skillos.negmarket — 负样本市场 (Negative Sample Market)

功能:
  - 负样本脱敏上传（四步脱敏流水线）
  - 加密分片存储（AES-256-GCM）
  - 反模式 Skill 自动生成
  - 调用时动态脱敏输出
  - 零知识验证（模拟）
"""

from skillos.negmarket.anti_pattern import AntiPatternGenerator
from skillos.negmarket.desensitizer import DesensitizationPipeline
from skillos.negmarket.models import (
    AntiPatternResult,
    AntiPatternSkill,
    DesensitizationContext,
    NegativeSample,
    ZKProof,
)
from skillos.negmarket.storage import SQLiteNegMarketStorage, StorageBackend
from skillos.negmarket.zk_verifier import ZKVerifier

__all__ = [
    "AntiPatternGenerator",
    "AntiPatternResult",
    "AntiPatternSkill",
    "DesensitizationContext",
    "DesensitizationPipeline",
    "NegativeSample",
    "SQLiteNegMarketStorage",
    "StorageBackend",
    "ZKProof",
    "ZKVerifier",
]
