from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable
from urllib.parse import urlparse


class HallucinationRisk(IntEnum):
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class HallucinationResult:
    risk: HallucinationRisk = HallucinationRisk.SAFE
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Citation:
    url: str
    claim: str
    status: str = "unverified"


class CitationVerifier:
    def __init__(self, fetcher: Callable[[str], str] | None = None) -> None:
        self._fetcher = fetcher

    @staticmethod
    def check_url_structure(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return all([parsed.scheme in ("http", "https"), bool(parsed.netloc)])
        except Exception:
            return False

    def verify_citation(self, citation: Citation) -> Citation:
        if not citation.url:
            citation.status = "missing"
            return citation
        if not self.check_url_structure(citation.url):
            citation.status = "missing"
        elif self._fetcher is not None:
            try:
                self._fetcher(citation.url)
                citation.status = "verified"
            except Exception:
                citation.status = "contradicted"
        else:
            citation.status = "verified"
        return citation

    def verify_citations(self, citations: list[Citation]) -> list[Citation]:
        return [self.verify_citation(c) for c in citations]


class SelfConsistencyCheck:
    @staticmethod
    def check_numerical_consistency(values: dict[str, float], context: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        for key, val in values.items():
            kl = key.lower()
            if "percent" in kl or "rate" in kl:
                if val > 100.0:
                    issues.append(f"{key}={val} exceeds 100%")
            if "prob" in kl and val > 1.0:
                issues.append(f"{key}={val} exceeds 1.0 for probability")
        if "total" in context:
            total = context["total"]
            sum_vals = sum(values.values())
            if abs(sum_vals - total) > 0.001 and sum_vals > total:
                issues.append(f"sum of values ({sum_vals}) > total ({total})")
        if "max_value" in context:
            max_val = context["max_value"]
            for key, val in values.items():
                if val > max_val:
                    issues.append(f"{key}={val} exceeds max_value={max_val}")
        return issues

    @staticmethod
    def check_contradiction(statements: list[str], context: list[str]) -> list[str]:
        contradictions: list[str] = []

        def _words(s: str) -> set[str]:
            return {w.lower().strip(".,!?;:") for w in s.split() if len(w) > 2}

        for i, s1 in enumerate(statements):
            w1 = _words(s1)
            for j, s2 in enumerate(context):
                w2 = _words(s2)
                overlap = w1 & w2
                if len(overlap) >= 3:
                    contradictions.append(
                        f"Statement {i} and context {j} share {len(overlap)} words: {overlap}"
                    )
        return contradictions

    @staticmethod
    def check_date_consistency(dates: list[str]) -> list[str]:
        issues: list[str] = []
        parsed: list[tuple[int, int, int]] = []
        patterns = [
            re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"),
            re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$"),
        ]
        for d in dates:
            matched = False
            for pat in patterns:
                m = pat.match(d)
                if m:
                    y, mo, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if mo < 1 or mo > 12 or day < 1 or day > 31:
                        issues.append(f"Invalid date value: {d}")
                    else:
                        parsed.append((y, mo, day))
                    matched = True
                    break
            if not matched:
                issues.append(f"Invalid date format: {d}")
        for i in range(len(parsed)):
            for j in range(i + 1, len(parsed)):
                if parsed[i] > parsed[j]:
                    issues.append(f"Date chronology issue: {dates[i]} > {dates[j]}")
        return issues

    @staticmethod
    def check_entity_references(entities: list[str], known_entities: set[str]) -> list[str]:
        issues: list[str] = []
        known_lower = {e.lower() for e in known_entities}
        for entity in entities:
            if entity.lower() not in known_lower:
                issues.append(f"Unknown entity: {entity}")
        return issues


_URL_PATTERN = re.compile(r"https?://[^\s,)\]]+")
_PERCENTAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DATE_PATTERN = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")


class HallucinationDetector:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    @staticmethod
    def _risk_from_score(score: float) -> HallucinationRisk:
        if score >= 0.8:
            return HallucinationRisk.CRITICAL
        if score >= 0.5:
            return HallucinationRisk.HIGH
        if score >= 0.25:
            return HallucinationRisk.MEDIUM
        if score >= 0.1:
            return HallucinationRisk.LOW
        return HallucinationRisk.SAFE

    def analyze_output(self, text: str, context: dict[str, Any] | None = None) -> HallucinationResult:
        if not text or text is None:
            return HallucinationResult()

        context = context or {}
        reasons: list[str] = []
        details: dict[str, Any] = {}
        score = 0.0

        urls = _URL_PATTERN.findall(text)
        if urls:
            unverifiable = [u for u in urls if not CitationVerifier.check_url_structure(u)]
            if unverifiable:
                reasons.append(f"Found {len(unverifiable)} unverifiable URL(s)")
                score += min(0.3 * len(unverifiable), 0.6)
                details["unverifiable_urls"] = unverifiable

        percentages = _PERCENTAGE_PATTERN.findall(text)
        numeric_issues: list[str] = []
        for p in percentages:
            if float(p) > 100:
                numeric_issues.append(f"Percentage {p}% exceeds 100")
        if numeric_issues:
            reasons.extend(numeric_issues)
            score += min(0.3 * len(numeric_issues), 0.6)
            details["numeric_issues"] = numeric_issues

        dates = _DATE_PATTERN.findall(text)
        formatted_dates = [f"{y}-{m}-{d}" for y, m, d in dates]
        if len(formatted_dates) >= 2:
            date_issues = SelfConsistencyCheck.check_date_consistency(formatted_dates)
            if date_issues:
                reasons.extend(date_issues)
                score += min(0.1 * len(date_issues), 0.3)
                details["date_issues"] = date_issues

        known_entities: set[str] = set(context.get("known_entities", []))
        if known_entities:
            text_entities = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
            entity_issues = SelfConsistencyCheck.check_entity_references(
                list(set(text_entities)), known_entities
            )
            if entity_issues:
                reasons.extend(entity_issues[:5])
                score += min(0.1 * len(entity_issues), 0.3)
                details["entity_issues"] = entity_issues

        statements = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 10]
        context_statements: list[str] = context.get("reference_statements", [])
        if context_statements and statements:
            contradictions = SelfConsistencyCheck.check_contradiction(statements, context_statements)
            if contradictions:
                reasons.extend(contradictions[:3])
                score += min(0.1 * len(contradictions), 0.3)
                details["contradictions"] = contradictions

        score = min(score, 1.0)
        risk = self._risk_from_score(score)

        return HallucinationResult(
            risk=risk,
            score=score,
            reasons=reasons,
            details=details,
        )
