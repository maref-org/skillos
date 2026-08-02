"""Retrieval policy — scores documents by relevance to a task.

Layer 1 of the RL-optimized document selection system.
Initial weights are hand-tuned; optimized by GRPO via train_retrieval_policy.py.

Usage:
    from skillos.retrieval.policy import RetrievalPolicy

    policy = RetrievalPolicy()
    docs = policy.score(task_tags=["audit", "meta"], task_type="release_gate")
    # docs = [(score, path), ...] sorted descending
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_WEIGHTS_PATH = Path("data/retrieval_weights.json")
_DEFAULT_WEIGHTS = {
    "tag_match": 0.40,
    "freshness": 0.25,
    "cross_ref": 0.20,
    "base_boost": 0.15,
}

_TYPE_BOOST = {
    "directory_root": 0.2,
    "directory_workspace": 0.15,
    "source_root": 2.0,
    "source_module": 1.5,
    "docs_index": 1.0,
    "directory": 0.1,
    "directory_archive": -0.3,
    "directory_ephemeral": -0.5,
    "document_map": 3.0,
    "design_doc": 0.8,
}

_STALE_DAYS = 90


class RetrievalPolicy:
    def __init__(self, weights_path: str | Path | None = None):
        self._path = Path(weights_path or _WEIGHTS_PATH)
        self._weights = self._load_weights()

    def _load_weights(self) -> dict[str, float]:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                return {**_DEFAULT_WEIGHTS, **data}
            except (json.JSONDecodeError, OSError):
                pass
        return dict(_DEFAULT_WEIGHTS)

    def _parse_frontmatter(self, text: str) -> dict[str, Any]:
        if not text.startswith("---"):
            return {}
        end = text.find("---", 3)
        if end == -1:
            return {}
        import yaml  # type: ignore[import-untyped]
        try:
            return yaml.safe_load(text[3:end]) or {}
        except yaml.YAMLError:
            return {}

    def score(
        self,
        task_tags: list[str] | None = None,
        task_type: str | None = None,
        doc_path: str = "",
        doc_text: str = "",
    ) -> float:
        fm = self._parse_frontmatter(doc_text)
        if not fm:
            return 0.0

        tag_score = self._tag_similarity(task_tags or [], fm.get("tags", []))
        freshness_score = self._freshness_score(fm.get("freshness", {}))
        boost = _TYPE_BOOST.get(fm.get("type", ""), 0.0)
        cross_ref_score = self._cross_ref_score(fm.get("cross_reference", []))
        weight = self._weights

        total = (
            weight["tag_match"] * tag_score
            + weight["freshness"] * freshness_score
            + weight["cross_ref"] * cross_ref_score
            + weight["base_boost"] * boost
        )
        return round(total, 4)

    def _tag_similarity(self, task_tags: list[str], doc_tags: list[str]) -> float:
        if not task_tags or not doc_tags:
            return 0.0
        task_set = set(t.lower() for t in task_tags)
        doc_set = set(t.lower() for t in doc_tags)
        if not task_set or not doc_set:
            return 0.0
        intersection = task_set & doc_set
        jaccard = len(intersection) / len(task_set | doc_set)
        return jaccard

    def _freshness_score(self, freshness: dict) -> float:
        updated_str = freshness.get("updated", "")
        if not updated_str:
            return 0.3
        try:
            updated = time.mktime(time.strptime(updated_str, "%Y-%m-%d"))
        except (ValueError, OverflowError):
            return 0.3
        age_days = (time.time() - updated) / 86400
        if age_days > _STALE_DAYS:
            return 0.0
        return max(0.0, 1.0 - age_days / _STALE_DAYS)

    def _cross_ref_score(self, cross_refs: list) -> float:
        """Score based on cross-reference richness (0-1).

        Documents with more cross-references are better connected
        in the knowledge graph, indicating higher reuse value.
        """
        if not cross_refs:
            return 0.0
        return min(1.0, len(cross_refs) / 5.0)

    def rank(
        self,
        task_tags: list[str] | None = None,
        task_type: str | None = None,
        candidates: list[tuple[str, str]] | None = None,
        top_k: int = 5,
    ) -> list[tuple[float, str]]:
        scored = []
        for path, text in (candidates or []):
            s = self.score(task_tags=task_tags, task_type=task_type, doc_path=path, doc_text=text)
            if s > 0:
                scored.append((s, path))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    def update_weights(self, new_weights: dict[str, float]) -> None:
        self._weights.update(new_weights)
        _WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _WEIGHTS_PATH.write_text(json.dumps(self._weights, indent=2))
