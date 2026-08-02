from __future__ import annotations

from skillos.security.hallucination_detector import (
    Citation,
    CitationVerifier,
    HallucinationDetector,
    HallucinationResult,
    HallucinationRisk,
    SelfConsistencyCheck,
)


class TestHallucinationRisk:
    def test_enum_values(self) -> None:
        assert HallucinationRisk.SAFE.value == 0
        assert HallucinationRisk.LOW.value == 1
        assert HallucinationRisk.MEDIUM.value == 2
        assert HallucinationRisk.HIGH.value == 3
        assert HallucinationRisk.CRITICAL.value == 4

    def test_ordered_by_severity(self) -> None:
        assert HallucinationRisk.SAFE < HallucinationRisk.LOW
        assert HallucinationRisk.LOW < HallucinationRisk.MEDIUM
        assert HallucinationRisk.MEDIUM < HallucinationRisk.HIGH
        assert HallucinationRisk.HIGH < HallucinationRisk.CRITICAL


class TestCitationVerifier:
    def test_check_url_structure_valid_https(self) -> None:
        assert CitationVerifier.check_url_structure("https://example.com")

    def test_check_url_structure_valid_http(self) -> None:
        assert CitationVerifier.check_url_structure("http://example.com/path")

    def test_check_url_structure_invalid_no_scheme(self) -> None:
        assert not CitationVerifier.check_url_structure("example.com")

    def test_check_url_structure_invalid_ftp(self) -> None:
        assert not CitationVerifier.check_url_structure("ftp://example.com")

    def test_check_url_structure_invalid_empty(self) -> None:
        assert not CitationVerifier.check_url_structure("")

    def test_check_url_structure_invalid_random(self) -> None:
        assert not CitationVerifier.check_url_structure("not-a-url")

    def test_verify_citation_valid_url(self) -> None:
        verifier = CitationVerifier()
        citation = Citation(url="https://example.com", claim="test claim")
        result = verifier.verify_citation(citation)
        assert result.status == "verified"

    def test_verify_citation_invalid_url(self) -> None:
        verifier = CitationVerifier()
        citation = Citation(url="not-a-url", claim="test claim")
        result = verifier.verify_citation(citation)
        assert result.status == "missing"

    def test_verify_citation_empty_url(self) -> None:
        verifier = CitationVerifier()
        citation = Citation(url="", claim="test claim")
        result = verifier.verify_citation(citation)
        assert result.status == "missing"

    def test_verify_citation_malformed_scheme(self) -> None:
        verifier = CitationVerifier()
        citation = Citation(url="ftp://example.com", claim="test claim")
        result = verifier.verify_citation(citation)
        assert result.status == "missing"

    def test_verify_citations_multiple(self) -> None:
        verifier = CitationVerifier()
        citations = [
            Citation(url="https://valid.com", claim="c1"),
            Citation(url="invalid", claim="c2"),
        ]
        results = verifier.verify_citations(citations)
        assert results[0].status == "verified"
        assert results[1].status == "missing"

    def test_verify_citation_with_fetcher_success(self) -> None:
        def mock_fetcher(url: str) -> str:
            return "content"
        verifier = CitationVerifier(fetcher=mock_fetcher)
        citation = Citation(url="https://example.com", claim="test")
        result = verifier.verify_citation(citation)
        assert result.status == "verified"

    def test_verify_citation_with_fetcher_failure(self) -> None:
        def mock_fetcher(url: str) -> str:
            raise ValueError("fetch failed")
        verifier = CitationVerifier(fetcher=mock_fetcher)
        citation = Citation(url="https://example.com", claim="test")
        result = verifier.verify_citation(citation)
        assert result.status == "contradicted"


class TestSelfConsistencyCheck:
    def test_numerical_consistency_normal(self) -> None:
        values = {"rate": 75.0, "percent": 50.0}
        issues = SelfConsistencyCheck.check_numerical_consistency(values, {})
        assert issues == []

    def test_numerical_consistency_percentage_over_100(self) -> None:
        values = {"percentage": 150.0}
        issues = SelfConsistencyCheck.check_numerical_consistency(values, {})
        assert any("exceeds 100%" in i for i in issues)

    def test_numerical_consistency_probability_over_1(self) -> None:
        values = {"probability": 1.5}
        issues = SelfConsistencyCheck.check_numerical_consistency(values, {})
        assert any("probability" in i for i in issues)

    def test_numerical_consistency_sum_vs_total(self) -> None:
        values = {"a": 60.0, "b": 50.0}
        issues = SelfConsistencyCheck.check_numerical_consistency(values, {"total": 100.0})
        assert any("sum" in i and "total" in i for i in issues)

    def test_numerical_consistency_vs_max_value(self) -> None:
        values = {"speed": 200.0}
        issues = SelfConsistencyCheck.check_numerical_consistency(values, {"max_value": 150.0})
        assert any("exceeds max_value" in i for i in issues)

    def test_contradiction_detected(self) -> None:
        statements = ["The sky is blue and clear today"]
        context = ["The sky is blue and full of clouds"]
        issues = SelfConsistencyCheck.check_contradiction(statements, context)
        assert len(issues) >= 1

    def test_contradiction_no_false_positive(self) -> None:
        statements = ["Python is a programming language"]
        context = ["Roses are red and violets are blue"]
        issues = SelfConsistencyCheck.check_contradiction(statements, context)
        assert issues == []

    def test_contradiction_empty_inputs(self) -> None:
        assert SelfConsistencyCheck.check_contradiction([], []) == []

    def test_date_consistency_valid(self) -> None:
        dates = ["2024-01-01", "2024-12-31"]
        issues = SelfConsistencyCheck.check_date_consistency(dates)
        assert issues == []

    def test_date_consistency_chronology(self) -> None:
        dates = ["2025-01-01", "2024-12-31"]
        issues = SelfConsistencyCheck.check_date_consistency(dates)
        assert any("chronology" in i for i in issues)

    def test_date_consistency_invalid_format(self) -> None:
        dates = ["01-01-2024", "2024/12/31"]
        issues = SelfConsistencyCheck.check_date_consistency(dates)
        assert any("Invalid date format" in i for i in issues)

    def test_date_consistency_invalid_value(self) -> None:
        dates = ["2024-13-01"]
        issues = SelfConsistencyCheck.check_date_consistency(dates)
        assert any("Invalid date value" in i for i in issues)

    def test_entity_references_all_known(self) -> None:
        entities = ["Python", "JavaScript"]
        issues = SelfConsistencyCheck.check_entity_references(entities, {"Python", "JavaScript"})
        assert issues == []

    def test_entity_references_unknown(self) -> None:
        entities = ["Python", "MadeUpLang"]
        issues = SelfConsistencyCheck.check_entity_references(entities, {"Python"})
        assert any("MadeUpLang" in i for i in issues)

    def test_entity_references_case_insensitive(self) -> None:
        entities = ["python"]
        issues = SelfConsistencyCheck.check_entity_references(entities, {"Python"})
        assert issues == []

    def test_entity_references_empty(self) -> None:
        assert SelfConsistencyCheck.check_entity_references([], {"Python"}) == []


class TestHallucinationDetector:
    def test_analyze_clean_text_safe(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output("The sky is blue. Water is wet.")
        assert result.risk == HallucinationRisk.SAFE
        assert result.score == 0.0

    def test_analyze_unverifiable_urls_medium_or_higher(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output("See http:///path for details.")
        assert result.risk >= HallucinationRisk.MEDIUM
        assert "unverifiable" in " ".join(result.reasons).lower()

    def test_analyze_numerical_contradiction_medium_or_higher(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output("The success rate is 150%.")
        assert result.risk >= HallucinationRisk.MEDIUM
        assert any("exceeds 100" in r for r in result.reasons)

    def test_analyze_date_chronology_issue(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output("Event A happened on 2025-01-01. Event B happened on 2024-12-31.")
        assert result.risk >= HallucinationRisk.LOW

    def test_analyze_with_unknown_entities(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output(
            "Python and Flibber Flabber are both great.",
            context={"known_entities": ["Python"]},
        )
        assert "Flibber" in str(result.details)

    def test_analyze_with_contradiction_context(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output(
            "The big blue sky is full of clouds today.",
            context={"reference_statements": ["The big blue sky is clear today"]},
        )
        assert len(result.reasons) > 0

    def test_analyze_empty_text_safe(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output("")
        assert result.risk == HallucinationRisk.SAFE
        assert result.score == 0.0
        assert result.reasons == []

    def test_analyze_none_text_safe(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output(None)  # type: ignore[arg-type]
        assert result.risk == HallucinationRisk.SAFE
        assert result.score == 0.0

    def test_analyze_multiple_issues_accumulate(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output(
            "According to not-a-url, the rate is 200%. Event on 2025-01-01 and 2024-01-01.",
        )
        assert result.risk >= HallucinationRisk.MEDIUM
        assert result.score > 0.3

    def test_analyze_score_bounded(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output(
            "See not-a-url " * 20 + " 150% " * 20
        )
        assert result.score <= 1.0
        assert result.risk <= HallucinationRisk.CRITICAL

    def test_analyze_with_context_no_effect_on_clean(self) -> None:
        detector = HallucinationDetector()
        result = detector.analyze_output(
            "Python is a language.",
            context={"known_entities": ["Python"]},
        )
        assert result.risk == HallucinationRisk.SAFE


class TestHallucinationResult:
    def test_default_values(self) -> None:
        result = HallucinationResult()
        assert result.risk == HallucinationRisk.SAFE
        assert result.score == 0.0
        assert result.reasons == []
        assert result.details == {}

    def test_custom_values(self) -> None:
        result = HallucinationResult(
            risk=HallucinationRisk.HIGH,
            score=0.7,
            reasons=["issue 1"],
            details={"key": "val"},
        )
        assert result.risk == HallucinationRisk.HIGH
        assert result.score == 0.7
        assert result.reasons == ["issue 1"]
        assert result.details == {"key": "val"}
