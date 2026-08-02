"""Tests for skillos.retrieval.policy"""

import json
from pathlib import Path

import pytest

from skillos.retrieval.policy import RetrievalPolicy

SAMPLE_README_AUDIT = """---
schema_version: "1.0"
type: directory
purpose: "Audit reports"
tags: [audit, quality, release]
freshness:
  updated: "2026-07-28"
---
"""

SAMPLE_README_ARCHIVE = """---
schema_version: "1.0"
type: directory_archive
purpose: "Old archives"
tags: [audit, history]
freshness:
  updated: "2026-07-15"
---
"""

SAMPLE_NO_FM = """# No frontmatter
Just some text.
"""


@pytest.fixture
def policy():
    return RetrievalPolicy()


class TestRetrievalPolicy:
    def test_parse_frontmatter(self, policy):
        fm = policy._parse_frontmatter(SAMPLE_README_AUDIT)
        assert fm["type"] == "directory"
        assert fm["tags"] == ["audit", "quality", "release"]

    def test_parse_no_frontmatter(self, policy):
        fm = policy._parse_frontmatter(SAMPLE_NO_FM)
        assert fm == {}

    def test_tag_similarity_exact(self, policy):
        s = policy._tag_similarity(["audit", "release"], ["audit", "release", "quality"])
        assert s == 2 / 3  # Jaccard

    def test_tag_similarity_no_overlap(self, policy):
        s = policy._tag_similarity(["audit"], ["archive"])
        assert s == 0.0

    def test_tag_similarity_empty(self, policy):
        assert policy._tag_similarity([], ["audit"]) == 0.0
        assert policy._tag_similarity(["audit"], []) == 0.0

    def test_freshness_recent(self, policy):
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        s = policy._freshness_score({"updated": recent})
        assert s > 0.9

    def test_freshness_stale(self, policy):
        s = policy._freshness_score({"updated": "2026-01-01"})
        assert s == 0.0

    def test_freshness_no_date(self, policy):
        assert policy._freshness_score({}) == 0.3

    def test_score_audit_vs_archive(self, policy):
        score_audit = policy.score(task_tags=["audit", "release"], doc_text=SAMPLE_README_AUDIT)
        score_archive = policy.score(task_tags=["audit", "release"], doc_text=SAMPLE_README_ARCHIVE)
        assert score_audit > score_archive

    def test_score_no_frontmatter(self, policy):
        s = policy.score(task_tags=["audit"], doc_text=SAMPLE_NO_FM)
        assert s == 0.0

    def test_rank_order(self, policy):
        candidates = [
            ("audit.md", SAMPLE_README_AUDIT),
            ("archive.md", SAMPLE_README_ARCHIVE),
        ]
        ranked = policy.rank(task_tags=["audit", "release"], candidates=candidates, top_k=2)
        assert len(ranked) == 2
        assert ranked[0][1] == "audit.md"

    def test_rank_top_k(self, policy):
        candidates = [
            ("a.md", SAMPLE_README_AUDIT),
            ("b.md", SAMPLE_README_ARCHIVE),
            ("c.md", SAMPLE_README_AUDIT),
        ]
        ranked = policy.rank(task_tags=["audit", "release"], candidates=candidates, top_k=1)
        assert len(ranked) == 1

    def test_update_weights(self, policy):
        import os
        orig_path = "data/retrieval_weights.json"
        backup = None
        if os.path.exists(orig_path):
            backup = Path(orig_path).read_text()
        try:
            policy.update_weights({"tag_match": 0.5, "freshness": 0.25, "cross_ref": 0.15, "base_boost": 0.10})
            loaded = json.loads(Path(orig_path).read_text())
            assert loaded["tag_match"] == 0.5
        finally:
            if backup:
                Path(orig_path).write_text(backup)
            elif os.path.exists(orig_path):
                os.remove(orig_path)
