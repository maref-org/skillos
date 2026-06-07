"""Tests for desensitizer ML-powered PII analysis"""

from skillos.negmarket.desensitizer import (
    DesensitizationPipeline,
    LocalPIIReplaceStep,
    PresidioPIIAnalyzerStep,
)
from skillos.negmarket.models import DesensitizationContext


class TestPresidioPIIAnalyzerStep:
    def test_skip_when_not_available(self):
        step = PresidioPIIAnalyzerStep(analyzer=None)
        ctx = DesensitizationContext(raw_text="my email is test@example.com")
        result = step.process(ctx)
        assert result.extra.get("pii_types_found") is None
        assert result.desensitized_text == ""

    def test_pipeline_includes_presidio(self):
        pipeline = DesensitizationPipeline()
        assert isinstance(pipeline.steps[0], PresidioPIIAnalyzerStep)

    def test_pipeline_five_steps(self):
        pipeline = DesensitizationPipeline()
        assert len(pipeline.steps) == 5

    def test_presidio_fallback_with_mock(self, monkeypatch):
        import skillos.negmarket.desensitizer as d

        monkeypatch.setattr(d, "_PRESIDIO_AVAILABLE", False)
        step = PresidioPIIAnalyzerStep()
        ctx = DesensitizationContext(raw_text="some text")
        result = step.process(ctx)
        assert result.extra.get("pii_types_found") is None

    def test_integration_with_pipeline(self):
        pipeline = DesensitizationPipeline(
            steps=[
                PresidioPIIAnalyzerStep(analyzer=None),
                LocalPIIReplaceStep(),
            ]
        )
        ctx = DesensitizationContext(raw_text="my email is test@example.com and phone 13800138000")
        # We manually test since presidio may not be installed
        result = pipeline.steps[1].process(pipeline.steps[0].process(ctx))
        assert "<REDACTED:EMAIL>" in result.desensitized_text
        assert "<REDACTED:PHONE>" in result.desensitized_text
