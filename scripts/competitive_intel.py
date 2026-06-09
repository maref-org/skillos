#!/usr/bin/env python3
"""Competitive Intelligence Pipeline

Automated competitive analysis:
  - Competitor profile definitions with categories
  - Web scraping for competitor updates
  - Structured report generation (JSON + Markdown)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

import httpx
from bs4 import BeautifulSoup

from skillos.kernel.logging_config import get_logger

logger = get_logger(__name__)


class CompetitorCategory(StrEnum):
    AGENT_PLATFORM = "agent_platform"
    AGENT_FRAMEWORK = "agent_framework"
    AGENT_MARKETPLACE = "agent_marketplace"
    SKILL_OS = "skill_os"
    AI_CODING = "ai_coding"


@dataclass
class CompetitorProfile:
    name: str
    category: CompetitorCategory
    urls: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    founded_year: int | None = None
    website: str = ""


@dataclass
class IntelReport:
    competitor_name: str
    category: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    headline: str = ""
    summary: str = ""
    source_url: str = ""
    relevance_score: float = 0.0
    raw_text_snippet: str = ""
    sentiment: str = "neutral"


@dataclass
class CompetitiveAnalysisReport:
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    competitors_analyzed: int = 0
    reports: list[IntelReport] = field(default_factory=list)
    summary_markdown: str = ""


_DEFAULT_COMPETITORS: list[CompetitorProfile] = [
    CompetitorProfile(
        name="OpenAI Agents SDK",
        category=CompetitorCategory.AGENT_PLATFORM,
        urls=["https://openai.com/blog"],
        tags=["openai", "gpt", "agent-sdk", "function-calling"],
        description="OpenAI 的 Agent SDK 与函数调用平台",
        website="https://openai.com",
    ),
    CompetitorProfile(
        name="LangChain",
        category=CompetitorCategory.AGENT_FRAMEWORK,
        urls=["https://blog.langchain.dev"],
        tags=["langchain", "langgraph", "agent-framework"],
        description="LangChain/LangGraph 多 Agent 编排框架",
        website="https://langchain.com",
    ),
    CompetitorProfile(
        name="AutoGen",
        category=CompetitorCategory.AGENT_FRAMEWORK,
        urls=["https://microsoft.github.io/autogen/blog"],
        tags=["autogen", "multi-agent", "microsoft"],
        description="Microsoft AutoGen 多 Agent 对话框架",
        website="https://microsoft.github.io/autogen",
    ),
    CompetitorProfile(
        name="CrewAI",
        category=CompetitorCategory.AGENT_FRAMEWORK,
        urls=["https://docs.crewai.com"],
        tags=["crewai", "role-based", "agent-orchestration"],
        description="CrewAI 角色型 Agent 编排",
        website="https://crewai.com",
    ),
    CompetitorProfile(
        name="Claude Code",
        category=CompetitorCategory.AI_CODING,
        urls=["https://docs.anthropic.com/en/docs/claude-code"],
        tags=["anthropic", "claude", "coding-agent"],
        description="Anthropic Claude Code AI 编程助手",
        website="https://anthropic.com",
    ),
]


class WebScraper:
    def __init__(self, timeout: float = 10.0):
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)

    def fetch_text(self, url: str) -> str:
        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return ""

    def close(self) -> None:
        self._client.close()


class IntelAnalyzer:
    @staticmethod
    def compute_relevance(text: str, tags: list[str]) -> float:
        if not text or not tags:
            return 0.0
        text_lower = text.lower()
        hits = sum(1 for t in tags if t.lower() in text_lower)
        return min(1.0, hits / len(tags))

    @staticmethod
    def detect_sentiment(text: str) -> str:
        positive = {"launch", "release", "improve", "new", "upgrade", "breakthrough", "partner", "funding", "growth"}
        negative = {"vulnerability", "breach", "shutdown", "decline", "layoff", "lawsuit", "bug", "outage"}
        text_lower = text.lower()
        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    @staticmethod
    def extract_headline(text: str) -> str:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        for line in lines:
            if len(line) > 20 and len(line) < 200:
                return line[:120]
        return lines[0][:120] if lines else ""


class CompetitiveIntelPipeline:
    def __init__(self, competitors: list[CompetitorProfile] | None = None):
        self._competitors = _DEFAULT_COMPETITORS if competitors is None else competitors
        self._scraper = WebScraper()
        self._analyzer = IntelAnalyzer()

    def run(self) -> CompetitiveAnalysisReport:
        report = CompetitiveAnalysisReport()
        for competitor in self._competitors:
            for url in competitor.urls:
                text = self._scraper.fetch_text(url)
                if not text:
                    continue
                relevance = self._analyzer.compute_relevance(text, competitor.tags)
                intel = IntelReport(
                    competitor_name=competitor.name,
                    category=competitor.category.value,
                    headline=self._analyzer.extract_headline(text),
                    summary=text[:300],
                    source_url=url,
                    relevance_score=round(relevance, 4),
                    raw_text_snippet=text[:200],
                    sentiment=self._analyzer.detect_sentiment(text),
                )
                report.reports.append(intel)
        report.competitors_analyzed = len(self._competitors)
        report.summary_markdown = self._generate_summary(report)
        self._scraper.close()
        return report

    def _generate_summary(self, report: CompetitiveAnalysisReport) -> str:
        lines = [
            "# Competitive Intelligence Report",
            f"Generated: {report.generated_at}",
            f"Competitors analyzed: {report.competitors_analyzed}",
            "",
        ]
        if not report.reports:
            lines.append("_No intelligence data collected._")
            return "\n".join(lines)
        lines.append("## Summary")
        for intel in report.reports:
            lines.append(f"### {intel.competitor_name} ({intel.category})")
            lines.append(f"- **Sentiment:** {intel.sentiment}")
            lines.append(f"- **Relevance:** {intel.relevance_score:.2%}")
            lines.append(f"- **Headline:** {intel.headline}")
            lines.append(f"- **Source:** {intel.source_url}")
            lines.append("")
        lines.append("---")
        lines.append(f"_{len(report.reports)} intelligence items collected_")
        return "\n".join(lines)

    def to_json(self, report: CompetitiveAnalysisReport) -> str:
        return json.dumps(asdict(report), indent=2, ensure_ascii=False)

    def to_markdown(self, report: CompetitiveAnalysisReport) -> str:
        return self._generate_summary(report)

    def save_report(self, report: CompetitiveAnalysisReport, output_dir: str = "reports") -> tuple[str, str]:
        from pathlib import Path

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = str(out / f"competitive_intel_{ts}.json")
        md_path = str(out / f"competitive_intel_{ts}.md")
        Path(json_path).write_text(self.to_json(report))
        Path(md_path).write_text(self.to_markdown(report))
        return json_path, md_path
