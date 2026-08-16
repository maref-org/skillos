"""Tests for skillos.security.hallucination_llm — LLM 补强的幻觉检测"""

from __future__ import annotations

import pytest

from skillos.security.hallucination_detector import HallucinationRisk
from skillos.security.hallucination_llm import (
    LitellmConsistencyClient,
    LLMConsistencyClient,
    LLMEnhancedDetector,
    SelfConsistencyVerifier,
)

# ---------------------------------------------------------------------------
# Fake LLM client（测试用，不可用于生产）
# ---------------------------------------------------------------------------


class FakeConsistentClient(LLMConsistencyClient):
    """同一 prompt 恒返回同一答案（自洽）"""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        return "该模型参数为 7B，训练数据截至 2026 年。"


class FakeInconsistentClient(LLMConsistencyClient):
    """同一 prompt 每次返回不同答案（不自洽）"""

    def __init__(self) -> None:
        self._calls = 0

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        self._calls += 1
        if self._calls % 2:
            return "该模型参数为 7B，训练数据截至 2026 年。"
        return "该模型参数为 70B，训练数据截至 2024 年。"


class FailingClient(LLMConsistencyClient):
    """LLM 调用失败，应降级不阻断"""

    def complete(self, prompt: str, *, temperature: float = 0.0) -> str:
        raise RuntimeError("provider down")


# ---------------------------------------------------------------------------
# SelfConsistencyVerifier
# ---------------------------------------------------------------------------


class TestSelfConsistencyVerifier:
    def test_consistent_sampling_no_flags(self) -> None:
        verifier = SelfConsistencyVerifier(client=FakeConsistentClient(), n_samples=3)
        verdict = verifier.verify("模型参数 7B")
        assert verdict.consistent is True
        assert verdict.conflict_keys == []

    def test_inconsistent_sampling_flags(self) -> None:
        verifier = SelfConsistencyVerifier(client=FakeInconsistentClient(), n_samples=3)
        verdict = verifier.verify("模型参数 7B")
        assert verdict.consistent is False
        assert len(verdict.conflict_keys) >= 1

    def test_failing_client_degrades(self) -> None:
        """LLM 不可用时不应抛出，返回降级 verdict"""
        verifier = SelfConsistencyVerifier(client=FailingClient(), n_samples=3)
        verdict = verifier.verify("任意文本")
        assert verdict.consistent is False
        assert verdict.error is not None

    def test_client_none_skips(self) -> None:
        verifier = SelfConsistencyVerifier(client=None, n_samples=3)
        verdict = verifier.verify("任意文本")
        assert verdict.consistent is False
        assert verdict.skipped is True

    def test_extract_key_facts_captures_figures(self) -> None:
        verifier = SelfConsistencyVerifier(client=FakeConsistentClient())
        facts = verifier.extract_key_facts("该模型参数为 7B，2026 年发布。")
        assert any("7" in f for f in facts) or any("7B" in f for f in facts)


# ---------------------------------------------------------------------------
# LLMEnhancedDetector（组合规则 + self-consistency + 引用验证）
# ---------------------------------------------------------------------------


class TestLLMEnhancedDetector:
    def test_rule_only_path_unchanged(self) -> None:
        """无 LLM client 时等价于规则检测"""
        detector = LLMEnhancedDetector(client=None)
        result = detector.analyze_output("这是一个完全没有风险的安全文本。")
        assert result.risk == HallucinationRisk.SAFE

    def test_citation_contradiction_escalates(self) -> None:
        detector = LLMEnhancedDetector(
            client=FakeInconsistentClient(),
            cite_verifier_cb=lambda url: "与引用内容完全矛盾，参数应为 3B。",
        )
        result = detector.analyze_output(
            "该模型参数为 7B，详见 https://example.com/model-spec",
        )
        # URL 可解析 + 引用验证矛盾 → 风险 ≥ MEDIUM
        assert result.risk >= HallucinationRisk.MEDIUM
        assert len(result.reasons) >= 1

    def test_citation_support_keeps_low_risk(self) -> None:
        detector = LLMEnhancedDetector(
            client=None,
            cite_verifier_cb=lambda url: "引用内容支持该说法，参数为 7B。",
        )
        result = detector.analyze_output("该模型参数为 7B。")
        assert result.risk <= HallucinationRisk.LOW

    def test_unsupported_reasons_include_consistency(self) -> None:
        detector = LLMEnhancedDetector(client=FakeInconsistentClient())
        result = detector.analyze_output("该模型参数为 7B，训练数据截至 2026 年。")
        texts = " ".join(result.reasons)
        assert "consist" in texts.lower() or "自洽" in texts


class TestLitellmClient:
    def test_lazily_imports(self) -> None:
        """未安装 litellm 时应降级为 None 而非抛 ImportError"""
        try:
            import litellm  # noqa: F401

            client = LitellmConsistencyClient(model="gpt-4o-mini")
            assert client is not None
        except ImportError:
            with pytest.raises(RuntimeError):
                LitellmConsistencyClient(model="gpt-4o-mini")
