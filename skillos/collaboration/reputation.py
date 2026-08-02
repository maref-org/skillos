"""信任声誉引擎 — TrustReputationEngine（L4 协作层）

职责：
  - 对实体（Agent/Provider/Skill 作者）维护行为记录、评价、治理参与度
  - 输出信誉分：overall = 执行 0.4 + 评价 0.3 + 治理 0.2 + 参与 0.1
  - 默认中值：无数据的维度取 50（中值），无治理参与则参与项为 0

应用：
  - 三方案报价的成功率承诺来源（§3.2 设计文档）
  - 服务团队成员的准入与分权（L4 仲裁 / 验收节点）
"""

from dataclasses import dataclass
from typing import Any

__all__ = ["Action", "ReputationScore", "Review", "TrustReputationEngine"]

DEFAULT_MEDIAN = 50.0
EXECUTION_WEIGHT = 0.4
REVIEW_WEIGHT = 0.3
GOVERNANCE_WEIGHT = 0.2
PARTICIPATION_WEIGHT = 0.1
MAX_RATING = 5.0


@dataclass
class Action:
    action_type: str
    success: bool
    timestamp: float = 0.0


@dataclass
class Review:
    reviewer_id: str
    rating: float
    comment: str = ""
    timestamp: float = 0.0


@dataclass
class ReputationScore:
    agent_id: str
    total_actions: int = 0
    success_rate: float = 0.0
    total_reviews: int = 0
    peer_reviews: float = 0.0
    governance_participation: int = 0
    overall_score: float = 0.0


class TrustReputationEngine:
    def __init__(self) -> None:
        self._actions: dict[str, list[Action]] = {}
        self._reviews: dict[str, list[Review]] = {}
        self._governance: dict[str, int] = {}

    def record_action(self, entity_id: str, action: Action) -> None:
        self._actions.setdefault(entity_id, []).append(action)

    def add_review(self, entity_id: str, review: Review) -> None:
        self._reviews.setdefault(entity_id, []).append(review)

    def record_governance_participation(self, entity_id: str) -> None:
        self._governance[entity_id] = self._governance.get(entity_id, 0) + 1

    def get_reputation(self, entity_id: str) -> ReputationScore | None:
        if entity_id not in self._actions and entity_id not in self._reviews and entity_id not in self._governance:
            return None
        return self.calculate_reputation(entity_id)

    def calculate_reputation(self, entity_id: str) -> ReputationScore:
        actions = self._actions.get(entity_id, [])
        reviews = self._reviews.get(entity_id, [])
        governance_count = self._governance.get(entity_id, 0)

        total_actions = len(actions)
        success_rate = 0.0
        if total_actions > 0:
            success_rate = sum(1 for a in actions if a.success) / total_actions * 100.0
        execution_score = success_rate if total_actions > 0 else DEFAULT_MEDIAN

        total_reviews = len(reviews)
        peer_reviews = 0.0
        if total_reviews > 0:
            peer_reviews = sum(r.rating for r in reviews) / total_reviews / MAX_RATING * 100.0
        review_score = peer_reviews if total_reviews > 0 else DEFAULT_MEDIAN

        governance_score = DEFAULT_MEDIAN if governance_count > 0 else DEFAULT_MEDIAN

        overall = (
            execution_score * EXECUTION_WEIGHT
            + review_score * REVIEW_WEIGHT
            + governance_score * GOVERNANCE_WEIGHT
            + float(governance_count) * PARTICIPATION_WEIGHT
        )

        return ReputationScore(
            agent_id=entity_id,
            total_actions=total_actions,
            success_rate=round(success_rate, 2),
            total_reviews=total_reviews,
            peer_reviews=round(peer_reviews, 2),
            governance_participation=governance_count,
            overall_score=round(overall, 2),
        )

    def get_reputation_ranking(self, top_k: int | None = None) -> list[ReputationScore]:
        entities = set(self._actions) | set(self._reviews) | set(self._governance)
        scores = [self.calculate_reputation(e) for e in entities]
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        if top_k is not None:
            scores = scores[:top_k]
        return scores

    def reset_agent(self, entity_id: str) -> None:
        self._actions.pop(entity_id, None)
        self._reviews.pop(entity_id, None)
        self._governance.pop(entity_id, None)

    def get_agent_history(self, entity_id: str) -> dict[str, Any]:
        return {
            "actions": list(self._actions.get(entity_id, [])),
            "governance_count": self._governance.get(entity_id, 0),
        }
