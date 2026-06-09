#!/usr/bin/env python3
"""Anti-Pattern Generator — 反模式 Skill 生成器

从脱敏负样本提取反模式特征并生成为 SkillManifest。
调用反模式 Skill 时仅返回风险等级和抽象警告。
"""

import logging
from typing import Any

from skillos.negmarket.models import AntiPatternResult, AntiPatternSkill, NegativeSample

logger = logging.getLogger(__name__)

_RISK_WARNINGS: dict[str, str] = {
    "low": "该反模式在低风险场景下已记录，建议增加输入校验。",
    "medium": "该反模式存在中等风险，建议增加输入校验和重试机制。",
    "high": "该反模式存在高风险，建议增加输入校验、重试机制和人工审核流程。",
}

_DEFAULT_WARNING = "该反模式已被记录，调用时注意风险。"


class AntiPatternGenerator:
    """反模式 Skill 生成器"""

    def generate(self, sample: NegativeSample, agent_id: str) -> AntiPatternSkill:
        manifest: dict[str, Any] = {
            "name": f"anti-{sample.category}",
            "version": "1.0.0",
            "author": f"negmarket:{agent_id}",
            "description": self._build_description(sample),
            "metadata": {
                "risk_level": sample.risk_level,
                "category": sample.category,
                "negmarket": True,
                "original_sample_id": sample.id,
            },
            "price_per_call": sample.price_per_call,
        }
        skill = AntiPatternSkill(
            sample_id=sample.id,
            skill_manifest=manifest,
            generated_by=agent_id,
        )
        logger.info(
            "Anti-pattern skill %s generated from sample %s (risk=%s)",
            skill.id,
            sample.id,
            sample.risk_level,
        )
        return skill

    def call(self, skill: AntiPatternSkill, params: dict[str, Any] | None = None) -> AntiPatternResult:
        risk_level = skill.skill_manifest.get("metadata", {}).get("risk_level", "medium")
        warning = _RISK_WARNINGS.get(risk_level, _DEFAULT_WARNING)
        return AntiPatternResult(
            risk_level=risk_level,
            warning=warning,
            anti_pattern_id=skill.id,
        )

    @staticmethod
    def _build_description(sample: NegativeSample) -> str:
        pattern = sample.desensitized_pattern
        triggers = pattern.get("triggers", [])
        action = pattern.get("suggested_action", "review")
        trigger_str = ", ".join(triggers) if triggers else "unknown"
        return (
            f"反模式 Skill — 类别: {sample.category}, "
            f"风险等级: {sample.risk_level}, "
            f"触发词: {trigger_str}, "
            f"建议措施: {action}"
        )
