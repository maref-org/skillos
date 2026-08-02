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

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from skillos.audit import AuditEventType, log_audit
from skillos.security.prompt_guard import detect_prompt_injection
from skillos.types import (
    Approval,
    ApprovalStatus,
    ExecutionPath,
    Intent,
    IntentType,
)

logger = logging.getLogger(__name__)


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


class EntryKernel:
    """20/80 入口控制器 — 意图识别与分流"""

    HUMAN_GATE_THRESHOLD = 0.7

    def __init__(self, router: Any | None = None):
        self.router = router
        self._routing_history: list[RoutingDecision] = []
        self._approvals: dict[str, Approval] = {}
        self._approval_events: dict[str, threading.Event] = {}
        # RLock 保护 _approvals / _approval_events 的跨线程访问
        # （await_confirmation 阻塞时 confirm/reject 在其他线程唤醒；
        #  cancel_session 嵌套调用 reject_approval，故用 RLock）
        self._lock = threading.RLock()

    def _classify_intent(self, user_input: str) -> dict[str, Any]:
        """本地意图分类（替代 athena.core.intent_classifier）"""
        low = user_input.lower()
        if any(kw in low for kw in ("deploy", "发布", "执行", "run", "execute")):
            return {"intent": "execution", "confidence": 0.85}
        if any(kw in low for kw in ("分析", "analyze", "report", "总结")):
            return {"intent": "analysis", "confidence": 0.80}
        if any(kw in low for kw in ("查询", "search", "find", "什么是")):
            return {"intent": "query", "confidence": 0.75}
        return {"intent": "chat", "confidence": 0.60}

    def parse_intent(self, user_input: str) -> Intent:
        """自然语言解析为结构化意图"""
        # Prompt 注入检测：在意图分类前扫描用户输入，检测到则审计记录
        injection = detect_prompt_injection(user_input)
        if injection.is_injection:
            log_audit(
                AuditEventType.AUTH_FAILURE,
                "anonymous",
                "entry_kernel",
                "Prompt injection detected at parse_intent",
                {
                    "risk_score": round(injection.risk_score, 4),
                    "matched_patterns": injection.matched_patterns[:5],
                    "input_hash": hashlib.sha256(
                        user_input.encode("utf-8")
                    ).hexdigest()[:16],
                },
            )

        result = self._classify_intent(user_input)
        intent_type = _INTENT_MAP.get(result["intent"], IntentType.CHAT)
        confidence = result["confidence"]

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
            log_audit(
                AuditEventType.AUTH_SUCCESS,
                "system",
                "human_gate",
                "human_gate auto-approved (no gate required)",
                {"intent_type": intent.intent_type.value},
            )
            return Approval(status=ApprovalStatus.APPROVED)

        risk_level = self._assess_risk(intent)

        if risk_level == "high":
            logger.warning(
                "HIGH RISK gate triggered for intent: %s",
                intent.raw_input[:80],
            )
            log_audit(
                AuditEventType.AUTH_SUCCESS,
                "system",
                "human_gate",
                "human_gate PENDING (high risk) — gate triggered",
                {
                    "intent_type": intent.intent_type.value,
                    "risk_level": "high",
                    "raw_input_hash": hashlib.sha256(
                        intent.raw_input.encode("utf-8")
                    ).hexdigest()[:16],
                },
            )
            return self._register_approval(
                Approval(
                    status=ApprovalStatus.PENDING,
                    reasoning=f"High risk operation detected: {intent.raw_input[:60]}",
                )
            )

        if risk_level == "medium":
            log_audit(
                AuditEventType.AUTH_SUCCESS,
                "system",
                "human_gate",
                "human_gate PENDING (medium risk) — gate triggered",
                {
                    "intent_type": intent.intent_type.value,
                    "risk_level": "medium",
                },
            )
            return self._register_approval(
                Approval(
                    status=ApprovalStatus.PENDING,
                    reasoning="Medium risk operation requires review",
                )
            )

        log_audit(
            AuditEventType.AUTH_SUCCESS,
            "system",
            "human_gate",
            "human_gate approved (low risk)",
            {"intent_type": intent.intent_type.value, "risk_level": "low"},
        )
        return Approval(status=ApprovalStatus.APPROVED)

    # ------------------------------------------------------------------
    # Unified HITL Interrupt API (confirm / reject / pause / cancel / await)
    # ------------------------------------------------------------------

    def _register_approval(self, approval: Approval) -> Approval:
        """注册 PENDING 审批，使其可被 confirm/reject 解决。

        同时清理已决策的旧审批条目（APPROVED/REJECTED），防止 _approvals dict
        无限增长（内存泄漏防护）。已决策条目在被清理前仍可被
        ``await_confirmation()`` 读取（见测试 test_await_already_decided_returns_approval）。
        """
        with self._lock:
            if approval.status == ApprovalStatus.PENDING:
                # 清理已决策条目，保留 PENDING
                decided_ids = [
                    aid for aid, a in self._approvals.items()
                    if a.status != ApprovalStatus.PENDING
                ]
                for aid in decided_ids:
                    self._approvals.pop(aid, None)
                    self._approval_events.pop(aid, None)
                self._approvals[approval.approval_id] = approval
                self._approval_events[approval.approval_id] = threading.Event()
        return approval

    def confirm_approval(
        self,
        approval_id: str,
        decision_maker: str = "human",
    ) -> Approval | None:
        """确认审批 — PENDING → APPROVED（统一 confirm 信号）。

        Args:
            approval_id: 审批 ID（由 human_gate() 返回的 Approval.approval_id）
            decision_maker: 决策者标识

        Returns:
            更新后的 Approval，若 ID 不存在或非 PENDING 则返回 None
        """
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None or approval.status != ApprovalStatus.PENDING:
                return None

            approval.status = ApprovalStatus.APPROVED
            approval.human_decision = "confirmed"
            approval.decided_at = time.time()
            event = self._approval_events.pop(approval_id, None)

        # 锁外唤醒 + 审计（避免持锁时 IO）
        if event is not None:
            event.set()

        log_audit(
            AuditEventType.AUTH_SUCCESS,
            decision_maker,
            approval_id,
            "Approval confirmed via unified HITL API",
            {
                "session_id": approval.session_id,
                "reasoning": approval.reasoning,
            },
        )
        logger.info("Approval %s confirmed by %s", approval_id, decision_maker)
        return approval

    def reject_approval(
        self,
        approval_id: str,
        decision_maker: str = "human",
        reason: str = "",
    ) -> Approval | None:
        """拒绝审批 — PENDING → REJECTED（统一 reject 信号）。

        Args:
            approval_id: 审批 ID
            decision_maker: 决策者标识
            reason: 拒绝原因

        Returns:
            更新后的 Approval，若 ID 不存在或非 PENDING 则返回 None
        """
        with self._lock:
            approval = self._approvals.get(approval_id)
            if approval is None or approval.status != ApprovalStatus.PENDING:
                return None

            approval.status = ApprovalStatus.REJECTED
            approval.human_decision = "rejected"
            if reason:
                approval.reasoning = reason
            approval.decided_at = time.time()
            event = self._approval_events.pop(approval_id, None)

        # 锁外唤醒 + 审计
        if event is not None:
            event.set()

        log_audit(
            AuditEventType.AUTH_FAILURE,
            decision_maker,
            approval_id,
            "Approval rejected via unified HITL API",
            {
                "session_id": approval.session_id,
                "reason": reason or approval.reasoning,
            },
        )
        logger.info("Approval %s rejected by %s: %s", approval_id, decision_maker, reason)
        return approval

    def pause_for_review(
        self,
        intent: Intent,
        session_manager: Any,
        session_id: str,
    ) -> Approval:
        """暂停会话并创建 PENDING 审批（统一 pause 信号）。

        将 human_gate() 与 SessionManager.pause_session() 统一接线：
        1. 调用 human_gate() 获取审批
        2. 若 PENDING，关联 session_id 并暂停会话
        3. 返回审批（可通过 await_confirmation() 等待）

        Args:
            intent: 触发审批的意图
            session_manager: SessionManager 实例
            session_id: 关联的会话 ID

        Returns:
            Approval 对象（PENDING 状态可后续 confirm/reject）
        """
        approval = self.human_gate(intent)
        if approval.status == ApprovalStatus.PENDING:
            approval.session_id = session_id
            try:
                session_manager.pause_session(session_id)
                logger.info(
                    "Session %s paused for approval %s review",
                    session_id,
                    approval.approval_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to pause session %s: %s", session_id, exc
                )
        return approval

    def cancel_session(
        self,
        session_manager: Any,
        session_id: str,
        reason: str = "",
    ) -> bool:
        """取消会话并拒绝关联的 PENDING 审批（统一 cancel 信号）。

        Args:
            session_manager: SessionManager 实例
            session_id: 要取消的会话 ID
            reason: 取消原因

        Returns:
            会话是否成功取消
        """
        # 查找并拒绝该 session 关联的所有 PENDING 审批
        # 快照后锁外 reject（reject_approval 会自己加锁，RLock 支持嵌套）
        with self._lock:
            pending_ids = [
                a.approval_id for a in self._approvals.values()
                if a.session_id == session_id
                and a.status == ApprovalStatus.PENDING
            ]
        for aid in pending_ids:
            self.reject_approval(
                aid,
                decision_maker="system",
                reason=f"session_cancelled: {reason}",
            )

        # 中止会话
        try:
            session_manager.abort_session(session_id)
            log_audit(
                AuditEventType.AUTH_FAILURE,
                "system",
                session_id,
                "Session cancelled via unified HITL API",
                {"reason": reason},
            )
            logger.info("Session %s cancelled: %s", session_id, reason)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to abort session %s: %s", session_id, exc)
            return False

    def await_confirmation(
        self,
        approval_id: str,
        timeout: float = 30.0,
    ) -> Approval | None:
        """等待人工确认（阻塞，带超时）。

        中断响应时间 ≤ 500ms 的 SLA 由调用方控制 timeout；
        此方法阻塞直到 confirm/reject 被调用或超时。

        Args:
            approval_id: 审批 ID
            timeout: 最大等待时间（秒），默认 30s

        Returns:
            已决策的 Approval，超时返回 None
        """
        # 取 event 引用（锁内），释放后阻塞 wait（不持锁等待）
        with self._lock:
            event = self._approval_events.get(approval_id)
        if event is None:
            # 已决策或不存在 — 直接返回当前状态
            with self._lock:
                return self._approvals.get(approval_id)

        if not event.wait(timeout=timeout):
            logger.warning(
                "await_confirmation timed out for %s (%.1fs)",
                approval_id,
                timeout,
            )
            return None

        with self._lock:
            return self._approvals.get(approval_id)

    def get_pending_approvals(self) -> list[Approval]:
        """获取所有待决策审批。"""
        with self._lock:
            return [
                a for a in self._approvals.values()
                if a.status == ApprovalStatus.PENDING
            ]

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
