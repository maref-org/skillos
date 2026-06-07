#!/usr/bin/env python3
"""Desensitizer — 四步脱敏流水线

步骤:
  1. Local PII Replace — 正则 + 规则引擎识别并替换敏感信息
  2. ZK Verify — 零知识承诺（委托 ZKVerifier）
  3. Anti-Pattern Skill Generate — 结构化反模式提取
  4. Dynamic Mask — 输出二次扫描 + 差分隐私扰动
"""

import hashlib
import re
from abc import ABC, abstractmethod
from typing import Any

from skillos.kernel.logging_config import get_logger
from skillos.negmarket.models import DesensitizationContext, NegativeSample
from skillos.negmarket.zk_verifier import ZKVerifier

logger = get_logger(__name__)

_PII_PATTERNS: list[tuple[str, str, str]] = [
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "email", "<REDACTED:EMAIL>"),
    (r"\b1[3-9]\d{9}\b", "phone", "<REDACTED:PHONE>"),
    (r"\b\d{17}[\dXx]\b", "id_card", "<REDACTED:ID_CARD>"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "ip", "<REDACTED:IP>"),
    (r"\b(?:sk-[a-zA-Z0-9]{20,}|pk-[a-zA-Z0-9]{20,}|[a-zA-Z0-9]{32,64})\b", "api_key", "<REDACTED:API_KEY>"),
]


class DesensitizationStep(ABC):
    @abstractmethod
    def process(self, ctx: DesensitizationContext) -> DesensitizationContext: ...


_HIGH_RISK_PII = {"api_key", "id_card"}


class LocalPIIReplaceStep(DesensitizationStep):
    def process(self, ctx: DesensitizationContext) -> DesensitizationContext:
        text = ctx.raw_text
        for pattern, pii_type, replacement in _PII_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                logger.info("PII replaced: %d %s instances", len(matches), pii_type)
                text = re.sub(pattern, replacement, text)
        ctx.desensitized_text = text
        pii_found = list(
            {pii_type for pattern, pii_type, _ in _PII_PATTERNS if re.search(pattern, ctx.raw_text)}
        )
        ctx.extra["pii_types_found"] = pii_found
        if any(p in _HIGH_RISK_PII for p in pii_found):
            ctx.risk_level = "high"
        return ctx


class ZKVerifyStep(DesensitizationStep):
    def __init__(self, verifier: ZKVerifier | None = None):
        self._verifier = verifier or ZKVerifier()

    def process(self, ctx: DesensitizationContext) -> DesensitizationContext:
        proof = self._verifier.prove(ctx.desensitized_text, ctx.contributor_id)
        ctx.extra["zk_proof"] = {
            "sample_id": proof.sample_id,
            "proof_value": proof.proof_value,
            "timestamp": proof.timestamp,
        }
        ctx.extra["original_hash"] = hashlib.sha256(ctx.raw_text.encode()).hexdigest()
        return ctx


class AntiPatternSkillStep(DesensitizationStep):
    def process(self, ctx: DesensitizationContext) -> DesensitizationContext:
        text = ctx.desensitized_text
        pattern: dict[str, Any] = {
            "category": ctx.category,
            "risk_level": ctx.risk_level,
            "triggers": self._extract_triggers(text),
            "suggested_action": self._suggest_action(ctx.risk_level),
        }
        ctx.extra["anti_pattern"] = pattern
        return ctx

    @staticmethod
    def _extract_triggers(text: str) -> list[str]:
        triggers = []
        error_keywords = ["fail", "error", "timeout", "crash", "denied", "reject", "invalid"]
        for kw in error_keywords:
            if kw in text.lower():
                triggers.append(kw)
        return triggers if triggers else ["unknown"]

    @staticmethod
    def _suggest_action(risk_level: str) -> str:
        suggestions = {
            "low": "增加输入校验",
            "medium": "增加输入校验 + 重试机制",
            "high": "增加输入校验 + 重试机制 + 人工审核",
        }
        return suggestions.get(risk_level, "review")


class DynamicMaskStep(DesensitizationStep):
    def process(self, ctx: DesensitizationContext) -> DesensitizationContext:
        text = ctx.desensitized_text
        for pattern, _, replacement in _PII_PATTERNS:
            text = re.sub(pattern, replacement, text)
        ctx.desensitized_text = text
        return ctx


class DesensitizationPipeline:
    """四步脱敏流水线"""

    def __init__(self, steps: list[DesensitizationStep] | None = None):
        self.steps = steps or [
            LocalPIIReplaceStep(),
            ZKVerifyStep(),
            AntiPatternSkillStep(),
            DynamicMaskStep(),
        ]

    def process(self, raw_text: str, contributor_id: str, category: str = "general") -> NegativeSample:
        ctx = DesensitizationContext(
            raw_text=raw_text,
            contributor_id=contributor_id,
            category=category,
        )
        for step in self.steps:
            ctx = step.process(ctx)

        sample = NegativeSample(
            contributor_id=contributor_id,
            original_hash=ctx.extra.get("original_hash", ""),
            encrypted_blob="",  # 由 Storage 层填充
            desensitized_pattern=ctx.extra.get("anti_pattern", {}),
            category=category,
            risk_level=ctx.risk_level,
        )
        return sample
