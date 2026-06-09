"""Tests for scripts.competitive_intel — competitive intelligence pipeline"""

from skillos.scripts.competitive_intel import (
    CompetitiveAnalysisReport,
    CompetitiveIntelPipeline,
    CompetitorCategory,
    CompetitorProfile,
    IntelAnalyzer,
    IntelReport,
)


class TestIntelAnalyzer:
    def setup_method(self):
        self.analyzer = IntelAnalyzer()

    def test_compute_relevance_full_match(self):
        score = self.analyzer.compute_relevance("openai launched new gpt model", ["openai", "gpt"])
        assert score > 0.5

    def test_compute_relevance_no_match(self):
        score = self.analyzer.compute_relevance("nothing about competitors", ["openai", "gpt"])
        assert score == 0.0

    def test_compute_relevance_empty_text(self):
        score = self.analyzer.compute_relevance("", ["tag1"])
        assert score == 0.0

    def test_compute_relevance_empty_tags(self):
        score = self.analyzer.compute_relevance("some text", [])
        assert score == 0.0

    def test_detect_sentiment_positive(self):
        assert self.analyzer.detect_sentiment("new breakthrough launch with funding") == "positive"

    def test_detect_sentiment_negative(self):
        assert self.analyzer.detect_sentiment("vulnerability breach and outage") == "negative"

    def test_detect_sentiment_neutral(self):
        assert self.analyzer.detect_sentiment("the system was updated") == "neutral"

    def test_extract_headline(self):
        text = "This is a very long text that should be used as headline\nSecond line"
        headline = self.analyzer.extract_headline(text)
        assert len(headline) > 0

    def test_extract_headline_empty(self):
        assert self.analyzer.extract_headline("") == ""


class TestCompetitiveIntelPipeline:
    def test_pipeline_with_mock_competitors(self, monkeypatch):
        competitors = [
            CompetitorProfile(
                name="TestCompetitor",
                category=CompetitorCategory.AGENT_PLATFORM,
                urls=["https://example.com"],
                tags=["test"],
            ),
        ]
        pipeline = CompetitiveIntelPipeline(competitors=competitors)
        monkeypatch.setattr(pipeline._scraper, "fetch_text", lambda url: "test content for tag matching")
        report = pipeline.run()
        assert report.competitors_analyzed == 1
        assert len(report.reports) >= 1

    def test_pipeline_empty_competitors(self):
        pipeline = CompetitiveIntelPipeline(competitors=[])
        report = pipeline.run()
        assert report.competitors_analyzed == 0
        assert len(report.reports) == 0

    def test_to_json_output(self, monkeypatch):
        competitors = [
            CompetitorProfile(
                name="C1",
                category=CompetitorCategory.AGENT_PLATFORM,
                urls=["https://example.com"],
                tags=["test"],
            ),
        ]
        pipeline = CompetitiveIntelPipeline(competitors=competitors)
        monkeypatch.setattr(pipeline._scraper, "fetch_text", lambda url: "test content")
        report = pipeline.run()
        json_str = pipeline.to_json(report)
        import json as j

        parsed = j.loads(json_str)
        assert "competitors_analyzed" in parsed
        assert parsed["competitors_analyzed"] == 1

    def test_to_markdown_output(self):
        report = CompetitiveAnalysisReport(
            competitors_analyzed=2,
            reports=[
                IntelReport(competitor_name="C1", category="agent_platform"),
            ],
        )
        pipeline = CompetitiveIntelPipeline(competitors=[])
        md = pipeline.to_markdown(report)
        assert "C1" in md
        assert "Competitive Intelligence Report" in md

    def test_save_report_creates_files(self, tmp_path, monkeypatch):
        competitors = [
            CompetitorProfile(
                name="C1",
                category=CompetitorCategory.AGENT_PLATFORM,
                urls=["https://example.com"],
                tags=["test"],
            ),
        ]
        pipeline = CompetitiveIntelPipeline(competitors=competitors)
        monkeypatch.setattr(pipeline._scraper, "fetch_text", lambda url: "test content")
        report = pipeline.run()
        json_path, md_path = pipeline.save_report(report, output_dir=str(tmp_path))
        import os

        assert os.path.exists(json_path)
        assert os.path.exists(md_path)

    def test_default_competitors_have_categories(self):
        from skillos.scripts.competitive_intel import _DEFAULT_COMPETITORS

        for c in _DEFAULT_COMPETITORS:
            assert c.category in CompetitorCategory

    def test_pipeline_no_fetch_on_scraper_failure(self, monkeypatch):
        competitors = [
            CompetitorProfile(
                name="C1",
                category=CompetitorCategory.AGENT_PLATFORM,
                urls=["https://fail.example"],
                tags=["test"],
            ),
        ]
        pipeline = CompetitiveIntelPipeline(competitors=competitors)
        monkeypatch.setattr(pipeline._scraper, "fetch_text", lambda url: "")
        report = pipeline.run()
        assert len(report.reports) == 0
