#!/usr/bin/env python3
"""Agent Scheduler — Agent 调度器

职责：
  - 根据任务复杂度分配 Agent（Gemma 4 / DeepSeek / Kimi）
  - 级联策略：置信度不足时升级模型
  - 拜占庭共识：3 模型输出比对

调度策略：
  - 简单任务 → 本地 Gemma 4（$0）
  - 中等任务 → DeepSeek V4
  - 复杂任务 → Kimi 2.6
  - 争议任务 → 多模型辩论（3 模型 + 多数决）
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable

from skillos.audit import AuditEventType, log_audit
from skillos.types import ModelTier, Task

logger = logging.getLogger(__name__)


_COMPLEXITY_THRESHOLDS = {
    "simple": 0.3,
    "medium": 0.6,
    "complex": 0.8,
}


@dataclass
class AgentAssignment:
    task_id: str
    assigned_model: str
    model_group: str
    estimated_cost_usd: float
    estimated_latency_ms: float
    fallback_chain: list[str]


class AgentExecutionError(Exception):
    """Agent 执行失败 — 所有 fallback 模型均已耗尽。"""


@dataclass
class ModelRoute:
    primary_model: str
    primary_group: str
    cascade_models: list[str]
    cascade_groups: list[str]


@dataclass
class ConsensusResult:
    consensus_text: str
    agreement_score: float
    model_votes: list[dict[str, Any]]
    arbitration_needed: bool
    pairwise_scores: list[float]


class AgentScheduler:
    """Agent 调度器 — 模型路由与共识"""

    MODEL_MAP = {
        ModelTier.FREE: ("gemma-4", "local", 0.0, 200.0),
        ModelTier.LOW: ("deepseek-chat", "primary", 0.003, 800.0),
        ModelTier.MEDIUM: ("moonshot-v1-8k", "secondary", 0.005, 1200.0),
        ModelTier.HIGH: ("moonshot-v1-32k", "secondary", 0.010, 2000.0),
    }

    BYZANTINE_FAULT_TOLERANCE = 1

    def __init__(self, router: Any | None = None, consensus_engine: Any | None = None):
        self.router = router
        self.consensus_engine = consensus_engine
        self._assignment_log: list[AgentAssignment] = []

    def schedule(self, task: Task) -> AgentAssignment:
        """根据任务复杂度分配 Agent"""
        complexity = task.complexity

        if complexity <= _COMPLEXITY_THRESHOLDS["simple"]:
            tier = ModelTier.FREE
        elif complexity <= _COMPLEXITY_THRESHOLDS["medium"]:
            tier = ModelTier.LOW
        elif complexity <= _COMPLEXITY_THRESHOLDS["complex"]:
            tier = ModelTier.MEDIUM
        else:
            tier = ModelTier.HIGH

        model, group, cost, latency = self.MODEL_MAP[tier]

        fallback = self._build_fallback_chain(tier)

        assignment = AgentAssignment(
            task_id=task.task_id,
            assigned_model=model,
            model_group=group,
            estimated_cost_usd=cost,
            estimated_latency_ms=latency,
            fallback_chain=fallback,
        )

        self._assignment_log.append(assignment)
        logger.info(
            "Scheduled task %s: model=%s group=%s cost=$%.4f",
            task.task_id,
            model,
            group,
            cost,
        )

        return assignment

    def execute_with_fallback(
        self,
        task: Task,
        assignment: AgentAssignment,
        execute_fn: Callable[[Task, str], Any],
    ) -> Any:
        """使用 fallback_chain 执行任务，失败自动重试（sub-agent 失败重试）。

        遍历 assignment.fallback_chain 中的 model group，依次尝试执行：
        1. 调用 execute_fn(task, model_group) 尝试执行
        2. 成功则返回结果（并记录审计日志）
        3. 失败则记录错误，尝试下一个 model group
        4. 全部失败则抛出 AgentExecutionError

        Args:
            task: 要执行的任务
            assignment: schedule() 返回的调度分配（含 fallback_chain）
            execute_fn: 执行函数，签名为 (task, model_group) -> result
                        执行失败时应抛出 Exception

        Returns:
            执行结果

        Raises:
            AgentExecutionError: 所有 fallback 模型均失败
        """
        chain = assignment.fallback_chain or [assignment.model_group]
        last_error: Exception | None = None
        attempted: list[dict[str, Any]] = []
        caller_id = task.metadata.get("caller_id", "unknown")

        for idx, model_group in enumerate(chain):
            try:
                result = execute_fn(task, model_group)
                # 成功
                log_audit(
                    AuditEventType.SKILL_EXECUTED,
                    caller_id,
                    task.task_id,
                    "execute_with_fallback succeeded"
                    if idx > 0
                    else "execute_with_fallback succeeded (primary)",
                    {
                        "model_group": model_group,
                        "attempt": idx + 1,
                        "total_attempts": len(chain),
                        "succeeded": True,
                    },
                )
                if idx > 0:
                    logger.info(
                        "Task %s succeeded on fallback #%d (group=%s)",
                        task.task_id,
                        idx + 1,
                        model_group,
                    )
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                attempted.append(
                    {
                        "model_group": model_group,
                        "error": str(exc),
                        "attempt": idx + 1,
                    }
                )
                logger.warning(
                    "Task %s failed on model_group=%s (attempt %d/%d): %s",
                    task.task_id,
                    model_group,
                    idx + 1,
                    len(chain),
                    exc,
                )

        # 所有 fallback 都失败
        log_audit(
            AuditEventType.SKILL_EXECUTED,
            caller_id,
            task.task_id,
            "execute_with_fallback exhausted all fallbacks",
            {
                "succeeded": False,
                "attempts": attempted,
                "total_attempts": len(chain),
            },
        )
        raise AgentExecutionError(
            f"All {len(chain)} fallback models exhausted for task {task.task_id}"
        ) from last_error

    def cascade(self, task: Task, confidence: float) -> ModelRoute:
        """级联策略：置信度不足时升级模型"""
        primary_model, primary_group, _, _ = self.MODEL_MAP[self._resolve_tier(task.complexity)]

        cascade_map = {
            ModelTier.FREE: (ModelTier.LOW, ModelTier.MEDIUM),
            ModelTier.LOW: (ModelTier.MEDIUM, ModelTier.HIGH),
            ModelTier.MEDIUM: (ModelTier.HIGH,),
            ModelTier.HIGH: (),
        }

        current_tier = self._resolve_tier(task.complexity)
        next_tiers = cascade_map.get(current_tier, ())

        cascade_models = []
        cascade_groups = []
        for t in next_tiers:
            m, g, _, _ = self.MODEL_MAP[t]
            cascade_models.append(m)
            cascade_groups.append(g)

        return ModelRoute(
            primary_model=primary_model,
            primary_group=primary_group,
            cascade_models=cascade_models,
            cascade_groups=cascade_groups,
        )

    async def byzantine_consensus(self, outputs: list[dict[str, Any]]) -> ConsensusResult:
        """拜占庭共识：多模型输出比对"""
        if self.consensus_engine:
            prompt: str = outputs[0].get("prompt", "")
            result = await self.consensus_engine.consensus(prompt)
            return ConsensusResult(
                consensus_text=result.consensus_text if hasattr(result, "consensus_text") else str(result),
                agreement_score=result.agreement_score if hasattr(result, "agreement_score") else 0.0,
                model_votes=[],
                arbitration_needed=result.arbitration_needed if hasattr(result, "arbitration_needed") else True,
                pairwise_scores=[],
            )

        texts = [o.get("text", "") for o in outputs]
        n = len(texts)

        if n < 2:
            return ConsensusResult(
                consensus_text=texts[0] if texts else "",
                agreement_score=1.0 if n == 1 else 0.0,
                model_votes=outputs,
                arbitration_needed=n == 0,
                pairwise_scores=[],
            )

        pairwise = self._compute_pairwise_similarity(texts)
        max_score = max(pairwise) if pairwise else 0.0

        agreement_threshold = 0.75
        arbitration_needed = max_score < agreement_threshold

        if not arbitration_needed:
            best_idx = self._find_majority_index(pairwise, n)
            consensus_text = texts[best_idx] if best_idx < n else texts[0]
        else:
            consensus_text = texts[0]

        return ConsensusResult(
            consensus_text=consensus_text,
            agreement_score=round(max_score, 4),
            model_votes=outputs,
            arbitration_needed=arbitration_needed,
            pairwise_scores=[round(s, 4) for s in pairwise],
        )

    def get_assignment_history(self) -> list[AgentAssignment]:
        return list(self._assignment_log)

    def get_cost_summary(self) -> dict[str, Any]:
        total_cost = sum(a.estimated_cost_usd for a in self._assignment_log)
        by_model: dict[str, int] = {}
        for a in self._assignment_log:
            by_model[a.assigned_model] = by_model.get(a.assigned_model, 0) + 1

        return {
            "total_assignments": len(self._assignment_log),
            "total_estimated_cost_usd": round(total_cost, 4),
            "by_model": by_model,
        }

    @staticmethod
    def _build_fallback_chain(tier: ModelTier) -> list[str]:
        chain_map = {
            ModelTier.FREE: ["local"],
            ModelTier.LOW: ["primary", "secondary", "local"],
            ModelTier.MEDIUM: ["secondary", "primary", "local"],
            ModelTier.HIGH: ["secondary", "primary"],
        }
        return chain_map.get(tier, ["primary"])

    @staticmethod
    def _resolve_tier(complexity: float) -> ModelTier:
        if complexity <= _COMPLEXITY_THRESHOLDS["simple"]:
            return ModelTier.FREE
        if complexity <= _COMPLEXITY_THRESHOLDS["medium"]:
            return ModelTier.LOW
        if complexity <= _COMPLEXITY_THRESHOLDS["complex"]:
            return ModelTier.MEDIUM
        return ModelTier.HIGH

    @staticmethod
    def _compute_pairwise_similarity(texts: list[str]) -> list[float]:
        scores = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                sim = AgentScheduler._jaccard_similarity(texts[i], texts[j])
                scores.append(sim)
        return scores

    @staticmethod
    def _jaccard_similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _find_majority_index(scores: list[float], n: int) -> int:
        if not scores or n <= 1:
            return 0
        from itertools import combinations
        pairs = list(combinations(range(n), 2))
        if not pairs:
            return 0
        best_idx = scores.index(max(scores))
        return pairs[best_idx][0]
