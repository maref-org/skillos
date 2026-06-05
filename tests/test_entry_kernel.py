"""Tests for skillos.kernel.entry_kernel - Entry Kernel with mocked intent_classifier"""

import time

import pytest

from skillos.kernel.entry_kernel import EntryKernel, RoutingDecision
from skillos._types import (
    Approval,
    ApprovalStatus,
    ExecutionPath,
    Intent,
    IntentType,
)


class TestRoutingDecision:
    def test_basic_fields(self):
        intent = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hello",
            parsed_query="hello",
            confidence=0.9,
        )
        decision = RoutingDecision(
            intent=intent,
            path=ExecutionPath.AGENT_AUTO,
        )
        assert decision.intent is intent
        assert decision.path == ExecutionPath.AGENT_AUTO
        assert decision.approval is None
        assert decision.risk_level == "low"
        assert decision.estimated_cost_usd == 0.0

    def test_approval_field(self):
        intent = Intent(
            intent_type=IntentType.EXECUTION,
            raw_input="test",
            parsed_query="test",
            confidence=0.9,
        )
        approval = Approval(status=ApprovalStatus.PENDING)
        decision = RoutingDecision(
            intent=intent,
            path=ExecutionPath.HUMAN_GUI,
            approval=approval,
        )
        assert decision.approval is approval
        assert decision.approval.status == ApprovalStatus.PENDING

    def test_timestamp_default(self):
        intent = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hi",
            parsed_query="hi",
            confidence=0.9,
        )
        before = time.time()
        decision = RoutingDecision(intent=intent, path=ExecutionPath.AGENT_AUTO)
        after = time.time()
        assert before <= decision.timestamp <= after


class TestEntryKernelInit:
    def test_default_init(self):
        ek = EntryKernel()
        assert ek.router is None
        assert ek._routing_history == []

    def test_init_with_router(self, mock_router):
        ek = EntryKernel(router=mock_router)
        assert ek.router is mock_router
        assert ek._routing_history == []


class TestParseIntent:
    @pytest.mark.parametrize(
        "classifier_intent,expected_type",
        [
            ("chat", IntentType.CHAT),
            ("query", IntentType.RESEARCH),
            ("analysis", IntentType.ANALYSIS),
            ("execution", IntentType.EXECUTION),
            ("unknown", IntentType.CHAT),
        ],
    )
    def test_intent_mapping(
        self, mock_intent_classifier, classifier_intent, expected_type
    ):
        mock_intent_classifier.return_value = {
            "intent": classifier_intent,
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("test input")
        assert intent.intent_type == expected_type

    def test_parse_sets_raw_input(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.85,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("hello world")
        assert intent.raw_input == "hello world"

    def test_parse_sets_parsed_query(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.85,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("  hello  ")
        assert intent.parsed_query == "hello"

    def test_parse_sets_confidence(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.77,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("test")
        assert intent.confidence == 0.77

    def test_human_gate_high_risk_keywords(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("删除所有数据")
        assert intent.requires_human_gate is True

    def test_human_gate_deploy_keywords(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("deploy to production")
        assert intent.requires_human_gate is True

    def test_human_gate_transfer_keywords(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("支付 100 元")
        assert intent.requires_human_gate is True

    def test_human_gate_medium_risk_keywords(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("create new project")
        assert intent.requires_human_gate is True

    def test_no_gate_for_safe_input(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("tell me a joke")
        assert intent.requires_human_gate is False

    def test_parse_calls_classifier(self, mock_intent_classifier):
        ek = EntryKernel()
        ek.parse_intent("test")
        mock_intent_classifier.assert_called_once_with("test")

    def test_case_insensitive_keyword_matching(self, mock_intent_classifier):
        mock_intent_classifier.return_value = {
            "intent": "chat",
            "confidence": 0.9,
        }
        ek = EntryKernel()
        intent = ek.parse_intent("DEPLOY TO PRODUCTION")
        assert intent.requires_human_gate is True


class TestRoute:
    def test_human_gui_when_requires_gate(self, simple_intent):
        simple_intent.requires_human_gate = True
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.path == ExecutionPath.HUMAN_GUI

    def test_human_gui_when_low_confidence(self, low_confidence_intent):
        ek = EntryKernel()
        decision = ek.route(low_confidence_intent)
        assert decision.path == ExecutionPath.HUMAN_GUI

    def test_agent_auto_for_chat(self, simple_intent):
        simple_intent.confidence = 0.9
        simple_intent.requires_human_gate = False
        simple_intent.intent_type = IntentType.CHAT
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.path == ExecutionPath.AGENT_AUTO

    def test_hybrid_for_non_chat(self, simple_intent):
        simple_intent.confidence = 0.9
        simple_intent.requires_human_gate = False
        simple_intent.intent_type = IntentType.RESEARCH
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.path == ExecutionPath.HYBRID

    def test_human_gui_approval_pending(self, simple_intent):
        simple_intent.requires_human_gate = True
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.approval is not None
        assert decision.approval.status == ApprovalStatus.PENDING

    def test_non_human_gui_no_approval(self, simple_intent):
        simple_intent.confidence = 0.9
        simple_intent.requires_human_gate = False
        simple_intent.intent_type = IntentType.CHAT
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.approval is None

    def test_risk_assessment_high(self, simple_intent):
        simple_intent.raw_input = "删除数据库"
        simple_intent.intent_type = IntentType.EXECUTION
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.risk_level == "high"

    def test_risk_assessment_deploy(self, simple_intent):
        simple_intent.raw_input = "deploy to production"
        simple_intent.intent_type = IntentType.EXECUTION
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.risk_level == "high"

    def test_risk_assessment_medium(self, simple_intent):
        simple_intent.raw_input = "update config"
        simple_intent.intent_type = IntentType.EXECUTION
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.risk_level == "medium"

    def test_risk_assessment_low(self, simple_intent):
        simple_intent.raw_input = "hello"
        simple_intent.intent_type = IntentType.CHAT
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.risk_level == "low"

    def test_cost_estimation_by_intent_type(self, simple_intent):
        ek = EntryKernel()
        simple_intent.intent_type = IntentType.CHAT
        simple_intent.confidence = 0.9
        decision = ek.route(simple_intent)
        assert decision.estimated_cost_usd == 0.001

    def test_cost_estimation_research(self, simple_intent):
        simple_intent.intent_type = IntentType.RESEARCH
        simple_intent.confidence = 0.9
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.estimated_cost_usd == 0.003

    def test_cost_estimation_analysis(self, simple_intent):
        simple_intent.intent_type = IntentType.ANALYSIS
        simple_intent.confidence = 0.9
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.estimated_cost_usd == 0.005

    def test_cost_estimation_execution(self, simple_intent):
        simple_intent.intent_type = IntentType.EXECUTION
        simple_intent.confidence = 0.9
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.estimated_cost_usd == 0.008

    def test_cost_estimation_content_creation(self, simple_intent):
        simple_intent.intent_type = IntentType.CONTENT_CREATION
        simple_intent.confidence = 0.9
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.estimated_cost_usd == 0.004

    def test_cost_estimation_skill_call(self, simple_intent):
        simple_intent.intent_type = IntentType.SKILL_CALL
        simple_intent.confidence = 0.9
        ek = EntryKernel()
        decision = ek.route(simple_intent)
        assert decision.estimated_cost_usd == 0.0

    def test_routing_history_appended(self, simple_intent):
        ek = EntryKernel()
        ek.route(simple_intent)
        assert len(ek._routing_history) == 1
        assert ek._routing_history[0].intent is simple_intent


class TestHumanGate:
    def test_auto_approved_when_no_gate_needed(self, simple_intent):
        simple_intent.requires_human_gate = False
        ek = EntryKernel()
        approval = ek.human_gate(simple_intent)
        assert approval.status == ApprovalStatus.APPROVED

    def test_high_risk_pending(self, simple_intent):
        simple_intent.requires_human_gate = True
        simple_intent.raw_input = "删除所有数据"
        ek = EntryKernel()
        approval = ek.human_gate(simple_intent)
        assert approval.status == ApprovalStatus.PENDING
        assert "High risk" in approval.reasoning

    def test_deploy_risk_pending(self, simple_intent):
        simple_intent.requires_human_gate = True
        simple_intent.raw_input = "deploy to production"
        ek = EntryKernel()
        approval = ek.human_gate(simple_intent)
        assert approval.status == ApprovalStatus.PENDING

    def test_medium_risk_pending(self, simple_intent):
        simple_intent.requires_human_gate = True
        simple_intent.raw_input = "create new resource"
        ek = EntryKernel()
        approval = ek.human_gate(simple_intent)
        assert approval.status == ApprovalStatus.PENDING
        assert approval.reasoning == "Medium risk operation requires review"

    def test_low_risk_approved_when_gate_required(self, simple_intent):
        simple_intent.requires_human_gate = True
        simple_intent.raw_input = "safe operation"
        ek = EntryKernel()
        approval = ek.human_gate(simple_intent)
        assert approval.status == ApprovalStatus.APPROVED

    def test_high_risk_contains_input_snippet(self, simple_intent):
        simple_intent.requires_human_gate = True
        simple_intent.raw_input = "转账 1000 元到测试账户"
        ek = EntryKernel()
        approval = ek.human_gate(simple_intent)
        assert "转账" in approval.reasoning


class TestRoutingStats:
    def test_empty_stats(self):
        ek = EntryKernel()
        stats = ek.get_routing_stats()
        assert stats == {"total": 0}

    def test_single_route_stats(self, simple_intent):
        ek = EntryKernel()
        simple_intent.confidence = 0.9
        simple_intent.intent_type = IntentType.CHAT
        ek.route(simple_intent)
        stats = ek.get_routing_stats()
        assert stats["total"] == 1
        assert "agent_auto" in stats["by_path"]
        assert stats["agent_auto_ratio"] == 1.0

    def test_multiple_route_stats(self, simple_intent):
        ek = EntryKernel()
        i1 = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hi",
            parsed_query="hi",
            confidence=0.9,
        )
        i2 = Intent(
            intent_type=IntentType.RESEARCH,
            raw_input="search",
            parsed_query="search",
            confidence=0.9,
        )
        ek.route(i1)
        ek.route(i2)
        stats = ek.get_routing_stats()
        assert stats["total"] == 2
        assert stats["agent_auto_ratio"] == 0.5
        assert stats["human_gui_ratio"] == 0.0

    def test_cost_aggregation(self, simple_intent):
        ek = EntryKernel()
        i1 = Intent(
            intent_type=IntentType.CHAT,
            raw_input="a",
            parsed_query="a",
            confidence=0.9,
        )
        i2 = Intent(
            intent_type=IntentType.RESEARCH,
            raw_input="b",
            parsed_query="b",
            confidence=0.9,
        )
        ek.route(i1)
        ek.route(i2)
        stats = ek.get_routing_stats()
        assert stats["total_estimated_cost_usd"] == pytest.approx(0.004, abs=1e-4)

    def test_risk_distribution(self, simple_intent):
        ek = EntryKernel()
        i1 = Intent(
            intent_type=IntentType.EXECUTION,
            raw_input="删除数据",
            parsed_query="删除数据",
            confidence=0.9,
        )
        i2 = Intent(
            intent_type=IntentType.CHAT,
            raw_input="hello",
            parsed_query="hello",
            confidence=0.9,
        )
        ek.route(i1)
        ek.route(i2)
        stats = ek.get_routing_stats()
        assert stats["by_risk"]["high"] == 1
        assert stats["by_risk"]["low"] == 1

    def test_human_gui_ratio_calculation(self):
        ek = EntryKernel()
        for _ in range(3):
            i = Intent(
                intent_type=IntentType.EXECUTION,
                raw_input="safe",
                parsed_query="safe",
                confidence=0.5,
                requires_human_gate=True,
            )
            ek.route(i)
        stats = ek.get_routing_stats()
        assert stats["human_gui_ratio"] == 1.0
