#!/usr/bin/env python3
"""Entry Kernel — 20/80 人类-AI 分流入口控制器

职责：
  - 自然语言输入 → 意图识别
  - 分流到 GUI（20%人类参与）或 Agent CLI（80%自动执行）
  - 关键决策点的人类审批门禁

技术栈：
  - 规则引擎（基于 intent_classifier）
  - 可选本地 Gemma 4 意图分类
  - Qwen-3 意图解析（通过 LiteLLM Router）
"""

import time
from dataclasses import dataclass, field
from typing import Any

from skillos._types import (
    Approval,
    ApprovalStatus,
    ExecutionPath,
    Intent,
    IntentType,
)
from skillos.kernel.logging_config import get_logger

logger = get_logger(__name__)


_INTENT_MAP = {
    "chat": IntentType.CHAT,
    "query": IntentType.RESEARCH,
    "analysis": IntentType.ANALYSIS,
    "execution": IntentType.EXECUTION,
}


_GATING_KEYWORDS = {
    "high_risk": ["删除", "deploy", "发布", "支付", "转账", "send money", "transfer"],
    "medium_risk": ["创建", "修改", "更新", "update", "create", "install"],
}


@dataclass
class RoutingDecision:
    intent: Intent
    path: ExecutionPath
    approval: Approval | None = None
    risk_level: str = "low"
    estimated_cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)


try:
    from athena.core.intent_classifier import classify_intent
except ImportError:
    classify_intent = None

try:
    from litellm import completion as litellm_completion
except ImportError:
    litellm_completion = None


class EntryKernel:
    """20/80 入口控制器 — 意图识别与分流"""

    HUMAN_GATE_THRESHOLD = 0.7

    def __init__(self, router: Any | None = None):
        self.router = router
        self._routing_history: list[RoutingDecision] = []

    def parse_intent(self, user_input: str) -> Intent:
        """自然语言解析为结构化意图"""
        if classify_intent is not None:
            result = classify_intent(user_input)
            intent_type = _INTENT_MAP.get(result["intent"], IntentType.CHAT)
            confidence = result["confidence"]
        elif litellm_completion is not None:
            intent_type, confidence = self._classify_with_llm(user_input)
        else:
            intent_type = self._classify_keyword(user_input)
            confidence = 0.5

        requires_gate = self._check_human_gate_required(intent_type, user_input)

        return Intent(
            intent_type=intent_type,
            raw_input=user_input,
            parsed_query=user_input.strip(),
            confidence=confidence,
            requires_human_gate=requires_gate,
        )

    def route(self, intent: Intent) -> RoutingDecision:
        """分流：20% GUI 人类参与 / 80% Agent 自主执行"""
        if intent.requires_human_gate or intent.confidence < self.HUMAN_GATE_THRESHOLD:
            path = ExecutionPath.HUMAN_GUI
        elif intent.intent_type == IntentType.CHAT:
            path = ExecutionPath.AGENT_AUTO
        else:
            path = ExecutionPath.HYBRID

        risk_level = self._assess_risk(intent)
        estimated_cost = self._estimate_cost(intent)

        decision = RoutingDecision(
            intent=intent,
            path=path,
            risk_level=risk_level,
            estimated_cost_usd=estimated_cost,
        )

        if path == ExecutionPath.HUMAN_GUI:
            decision.approval = Approval(status=ApprovalStatus.PENDING)

        self._routing_history.append(decision)
        logger.info(
            "Routing decision: intent=%s path=%s risk=%s",
            intent.intent_type.value,
            path.value,
            risk_level,
        )

        return decision

    def human_gate(self, intent: Intent) -> Approval:
        """人类审批门禁（关键决策点）"""
        if not intent.requires_human_gate:
            return Approval(status=ApprovalStatus.APPROVED)

        risk_level = self._assess_risk(intent)

        if risk_level == "high":
            logger.warning(
                "HIGH RISK gate triggered for intent: %s",
                intent.raw_input[:80],
            )
            return Approval(
                status=ApprovalStatus.PENDING,
                reasoning=f"High risk operation detected: {intent.raw_input[:60]}",
            )

        if risk_level == "medium":
            return Approval(
                status=ApprovalStatus.PENDING,
                reasoning="Medium risk operation requires review",
            )

        return Approval(status=ApprovalStatus.APPROVED)

    def get_routing_stats(self) -> dict[str, Any]:
        total = len(self._routing_history)
        if total == 0:
            return {"total": 0}

        by_path: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        total_cost = 0.0

        for d in self._routing_history:
            by_path[d.path.value] = by_path.get(d.path.value, 0) + 1
            by_risk[d.risk_level] = by_risk.get(d.risk_level, 0) + 1
            total_cost += d.estimated_cost_usd

        return {
            "total": total,
            "by_path": by_path,
            "by_risk": by_risk,
            "total_estimated_cost_usd": round(total_cost, 4),
            "human_gui_ratio": by_path.get("human_gui", 0) / total,
            "agent_auto_ratio": by_path.get("agent_auto", 0) / total,
        }

    def _classify_keyword(self, user_input: str) -> IntentType:
        """基于关键词的意图回退分类（athena.core 不可用时的 fallback）"""
        low = user_input.lower()
        for kw in _GATING_KEYWORDS.get("high_risk", []):
            if kw in low:
                return IntentType.EXECUTION
        if any(kw in low for kw in ["?", "?", "how", "what", "why", "search", "find"]) or "?" in user_input:
            return IntentType.RESEARCH
        if any(kw in low for kw in ["analyze", "analyse", "评估", "compare", "对比", "summary"]):
            return IntentType.ANALYSIS
        return IntentType.CHAT

    def _classify_with_llm(self, user_input: str, model: str = "gpt-4o-mini") -> tuple[IntentType, float]:
        if litellm_completion is None:
            return self._classify_keyword(user_input), 0.5
        try:
            import json
            response = litellm_completion(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        "Classify the user intent into one of: "
                        "skill_call, research, content_creation, analysis, execution, chat. "
                        "Respond with JSON: {\"intent\": \"...\", \"confidence\": 0.0-1.0}"
                    )},
                    {"role": "user", "content": user_input},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=50,
            )
            result = json.loads(response.choices[0].message.content)
            intent_type = _INTENT_MAP.get(result.get("intent", "chat"), IntentType.CHAT)
            confidence = float(result.get("confidence", 0.5))
            return intent_type, confidence
        except Exception as e:
            logger.warning("LLM classification failed, falling back to keyword: %s", e)
            return self._classify_keyword(user_input), 0.5

    def _check_human_gate_required(self, intent_type: IntentType, user_input: str) -> bool:
        low = user_input.lower()
        for keywords in _GATING_KEYWORDS.values():
            for kw in keywords:
                if kw in low:
                    return True
        return False

    def _assess_risk(self, intent: Intent) -> str:
        low = intent.raw_input.lower()
        for kw in _GATING_KEYWORDS.get("high_risk", []):
            if kw in low:
                return "high"
        for kw in _GATING_KEYWORDS.get("medium_risk", []):
            if kw in low:
                return "medium"
        return "low"

    def _estimate_cost(self, intent: Intent) -> float:
        cost_map = {
            IntentType.CHAT: 0.001,
            IntentType.RESEARCH: 0.003,
            IntentType.ANALYSIS: 0.005,
            IntentType.EXECUTION: 0.008,
            IntentType.CONTENT_CREATION: 0.004,
            IntentType.SKILL_CALL: 0.0,
        }
        return cost_map.get(intent.intent_type, 0.005)
