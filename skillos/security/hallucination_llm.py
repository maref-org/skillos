"""skillos.security.hallucination_llm — LLM 补强的幻觉检测

GA 前 P1 例外 #4：接入 LLM 后实现输出层幻觉检测（self-consistency + 引用验证）。

架构（与 outcome_contracts.LLMClient 同构）:
  - LLMConsistencyClient: 抽象接口（complete）。
  - LitellmConsistencyClient: litellm 实现（懒加载，未安装时构造抛 RuntimeError）。
  - SelfConsistencyVerifier: 多采样（n_samples）提取关键事实指纹，不一致判幻觉。
  - LLMEnhancedDetector: 组合既有规则检测（HallucinationDetector）+
    self-consistency + 引用验证，LLM 不可用时自动降级为纯规则路径，不阻断。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from skillos.security.hallucination_detector import (
    HallucinationDetector,
    HallucinationResult,
)

# 关键事实指纹：数字（含单位/百分号）
_FACT_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*[A-Za-z%B]*")
# 引用 URL
_URL_PATTERN = re.compile(r"https?://[^\s,)\]]+")
# 引用验证信号词（中英）
_SUPPORT_WORDS = ("支持", "一致", "符合", "confirm", "support", "consistent")
_CONTRADICT_WORDS = ("矛盾", "不一致", "否认", "contradict", "reject", "inconsistent")


class LLMConsistencyClient:
    """LLM 一致性采样抽象接口。实现方提供 complete()。"""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        raise NotImplementedError


class LitellmConsistencyClient(LLMConsistencyClient):
    """基于 litellm 的实现。构造时懒加载 litellm，未安装则抛 RuntimeError。"""

    def __init__(self, model: str, **kwargs: Any) -> None:
        try:
            import litellm  # noqa: F401
        except ImportError as exc:  # pragma: no cover - 取决于环境
            raise RuntimeError("litellm not installed; install skillos[llm]") from exc
        self._model = model
        self._kwargs = kwargs

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        import litellm

        resp = litellm.completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            **self._kwargs,
        )
        return resp["choices"][0]["message"]["content"]


@dataclass
class ConsistencyVerdict:
    consistent: bool = False
    conflict_keys: list[str] = field(default_factory=list)
    skipped: bool = False
    error: str | None = None


class SelfConsistencyVerifier:
    """多采样 self-consistency 校验。

    对同一输入做 n_samples 次独立采样，提取关键事实指纹（数字/单位），
    指纹集合不一致即判为不自洽（幻觉信号）。LLM 不可用或抛错时返回
    skipped/error verdict（不阻断调用方）。
    """

    def __init__(
        self,
        client: LLMConsistencyClient | None = None,
        n_samples: int = 3,
        temperature: float = 0.8,
    ) -> None:
        self._client = client
        self._n_samples = max(2, n_samples)
        self._temperature = temperature

    def extract_key_facts(self, text: str) -> set[str]:
        """提取文本中的关键事实指纹（数字及其单位/百分号）。"""
        return {m.strip() for m in _FACT_PATTERN.findall(text) if m.strip()}

    @staticmethod
    def _sample_prompt(text: str) -> str:
        return (
            "你是严谨的事实核查员。请仅输出该陈述中出现的具体数字类关键事实"
            "（数值+单位或年份），用逗号分隔，不要任何解释。\n陈述: " + text
        )

    def verify(self, text: str) -> ConsistencyVerdict:
        if self._client is None:
            return ConsistencyVerdict(skipped=True)
        if not text:
            return ConsistencyVerdict(consistent=True)

        seen: set[str] | None = None
        conflicts: set[str] = set()
        try:
            for _ in range(self._n_samples):
                raw = self._client.complete(self._sample_prompt(text), temperature=self._temperature)
                facts = self.extract_key_facts(raw)
                if seen is None:
                    seen = facts
                elif seen != facts:
                    conflicts |= seen ^ facts
        except Exception as exc:
            return ConsistencyVerdict(consistent=False, error=str(exc))

        conflict_list = sorted(conflicts)
        return ConsistencyVerdict(consistent=not conflict_list, conflict_keys=conflict_list)


class LLMEnhancedDetector:
    """组合式幻觉检测器：规则（HallucinationDetector）+ self-consistency + 引用验证。

    引用验证通过可选 cite_verifier_cb 注入（返回引用内容文本），
    用信号词判定支持/矛盾。LLM client 或 cb 缺失时不阻断，自动降级。
    """

    def __init__(
        self,
        client: LLMConsistencyClient | None = None,
        threshold: float = 0.5,
        cite_verifier_cb: Callable[[str], str] | None = None,
        n_samples: int = 3,
    ) -> None:
        self._client = client
        self._threshold = threshold
        self._cite_cb = cite_verifier_cb
        self._n_samples = n_samples
        self._rule_detector = HallucinationDetector(threshold=threshold)

    @staticmethod
    def _escalate(base: HallucinationResult, delta: float, reason: str) -> HallucinationResult:
        score = min(base.score + delta, 1.0)
        risk = HallucinationDetector._risk_from_score(score)
        return HallucinationResult(
            risk=risk,
            score=score,
            reasons=base.reasons + [reason],
            details=base.details,
        )

    def analyze_output(self, text: str, context: dict[str, Any] | None = None) -> HallucinationResult:
        if not text:
            return HallucinationResult()
        base = self._rule_detector.analyze_output(text, context)
        result = base

        if self._client is not None:
            verdict = SelfConsistencyVerifier(client=self._client, n_samples=self._n_samples).verify(text)
            if verdict.error:
                result = self._escalate(result, 0.05, f"LLM self-consistency unavailable: {verdict.error}")
            elif not verdict.consistent and not verdict.skipped:
                result = self._escalate(
                    result,
                    0.2,
                    "self-consistency 多采样不一致: " + ", ".join(verdict.conflict_keys[:5]),
                )
                result.details["consistency_conflicts"] = verdict.conflict_keys

        if self._cite_cb is not None:
            for url in _URL_PATTERN.findall(text):
                try:
                    citation_text = self._cite_cb(url) or ""
                except Exception as exc:  # 引用验证失败不阻断
                    citation_text = ""
                    result = self._escalate(result, 0.05, f"citation verify failed for {url}: {exc}")
                    continue
                lower = citation_text.lower()
                if any(w in lower for w in _CONTRADICT_WORDS):
                    result = self._escalate(result, 0.3, f"引用验证矛盾: {url}")
                    result.details["citation_contradictions"] = result.details.get("citation_contradictions", []) + [
                        url
                    ]
                elif any(w in lower for w in _SUPPORT_WORDS):
                    result.details.setdefault("citation_supported", []).append(url)

        return result
