"""Tests for skillos.kernel.agent_scheduler - Agent Scheduling, Cascade, Consensus"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from skillos._types import Task
from skillos.kernel.agent_scheduler import (
    AgentAssignment,
    AgentScheduler,
    ConsensusResult,
    ModelRoute,
)


class TestAgentAssignment:
    def test_all_fields(self):
        assignment = AgentAssignment(
            task_id="task-001",
            assigned_model="deepseek-chat",
            model_group="primary",
            estimated_cost_usd=0.003,
            estimated_latency_ms=800.0,
            fallback_chain=["primary", "secondary"],
        )
        assert assignment.task_id == "task-001"
        assert assignment.assigned_model == "deepseek-chat"
        assert assignment.model_group == "primary"
        assert assignment.estimated_cost_usd == 0.003
        assert assignment.estimated_latency_ms == 800.0
        assert assignment.fallback_chain == ["primary", "secondary"]


class TestModelRoute:
    def test_all_fields(self):
        route = ModelRoute(
            primary_model="gemma-4",
            primary_group="local",
            cascade_models=["deepseek-chat", "moonshot-v1-8k"],
            cascade_groups=["primary", "secondary"],
        )
        assert route.primary_model == "gemma-4"
        assert route.primary_group == "local"
        assert len(route.cascade_models) == 2
        assert len(route.cascade_groups) == 2


class TestConsensusResult:
    def test_all_fields(self):
        result = ConsensusResult(
            consensus_text="final answer",
            agreement_score=0.85,
            model_votes=[{"model": "a", "text": "x"}, {"model": "b", "text": "y"}],
            arbitration_needed=False,
            pairwise_scores=[0.8, 0.9, 0.75],
        )
        assert result.consensus_text == "final answer"
        assert result.agreement_score == 0.85
        assert len(result.model_votes) == 2
        assert result.arbitration_needed is False
        assert len(result.pairwise_scores) == 3


class TestAgentSchedulerInit:
    def test_default_init(self):
        scheduler = AgentScheduler()
        assert scheduler.router is None
        assert scheduler.consensus_engine is None
        assert scheduler._assignment_log == []

    def test_init_with_router(self, mock_router):
        scheduler = AgentScheduler(router=mock_router)
        assert scheduler.router is mock_router

    def test_init_with_consensus_engine(self, mock_consensus_engine):
        scheduler = AgentScheduler(consensus_engine=mock_consensus_engine)
        assert scheduler.consensus_engine is mock_consensus_engine


class TestSchedule:
    def test_simple_task_free_tier(self, simple_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(simple_task)
        assert assignment.assigned_model == "gemma-4"
        assert assignment.model_group == "local"
        assert assignment.estimated_cost_usd == 0.0

    def test_medium_task_low_tier(self, medium_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(medium_task)
        assert assignment.assigned_model == "deepseek-chat"
        assert assignment.model_group == "primary"
        assert assignment.estimated_cost_usd == 0.003

    def test_complex_task_medium_tier(self):
        task = Task(complexity=0.7)
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(task)
        assert assignment.assigned_model == "moonshot-v1-8k"
        assert assignment.model_group == "secondary"
        assert assignment.estimated_cost_usd == 0.005

    def test_very_complex_task_high_tier(self, complex_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(complex_task)
        assert assignment.assigned_model == "moonshot-v1-32k"
        assert assignment.model_group == "secondary"
        assert assignment.estimated_cost_usd == 0.010

    def test_boundary_simple_threshold(self):
        task = Task(complexity=0.3)
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(task)
        assert assignment.assigned_model == "gemma-4"

    def test_boundary_medium_threshold(self):
        task = Task(complexity=0.6)
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(task)
        assert assignment.assigned_model == "deepseek-chat"

    def test_boundary_complex_threshold(self):
        task = Task(complexity=0.8)
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(task)
        assert assignment.assigned_model == "moonshot-v1-8k"

    def test_above_complex_threshold(self):
        task = Task(complexity=0.81)
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(task)
        assert assignment.assigned_model == "moonshot-v1-32k"

    def test_assignment_has_task_id(self, simple_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(simple_task)
        assert assignment.task_id == simple_task.task_id

    def test_fallback_chain_for_free_tier(self, simple_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(simple_task)
        assert assignment.fallback_chain == ["local"]

    def test_fallback_chain_for_low_tier(self, medium_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(medium_task)
        assert assignment.fallback_chain == ["primary", "secondary", "local"]

    def test_fallback_chain_for_medium_tier(self):
        task = Task(complexity=0.7)
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(task)
        assert assignment.fallback_chain == ["secondary", "primary", "local"]

    def test_fallback_chain_for_high_tier(self, complex_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(complex_task)
        assert assignment.fallback_chain == ["secondary", "primary"]

    def test_latency_mapping_free(self, simple_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(simple_task)
        assert assignment.estimated_latency_ms == 200.0

    def test_latency_mapping_low(self, medium_task):
        scheduler = AgentScheduler()
        assignment = scheduler.schedule(medium_task)
        assert assignment.estimated_latency_ms == 800.0

    def test_logging_to_history(self, simple_task):
        scheduler = AgentScheduler()
        scheduler.schedule(simple_task)
        assert len(scheduler._assignment_log) == 1
        assert scheduler._assignment_log[0].task_id == simple_task.task_id


class TestCascade:
    def test_free_tier_cascade(self, simple_task):
        scheduler = AgentScheduler()
        route = scheduler.cascade(simple_task, confidence=0.5)
        assert route.primary_model == "gemma-4"
        assert route.primary_group == "local"
        assert route.cascade_models == ["deepseek-chat", "moonshot-v1-8k"]
        assert route.cascade_groups == ["primary", "secondary"]

    def test_low_tier_cascade(self, medium_task):
        scheduler = AgentScheduler()
        route = scheduler.cascade(medium_task, confidence=0.5)
        assert route.primary_model == "deepseek-chat"
        assert route.cascade_models == ["moonshot-v1-8k", "moonshot-v1-32k"]

    def test_medium_tier_cascade(self):
        task = Task(complexity=0.7)
        scheduler = AgentScheduler()
        route = scheduler.cascade(task, confidence=0.5)
        assert route.primary_model == "moonshot-v1-8k"
        assert route.cascade_models == ["moonshot-v1-32k"]
        assert len(route.cascade_groups) == 1

    def test_high_tier_no_cascade(self, complex_task):
        scheduler = AgentScheduler()
        route = scheduler.cascade(complex_task, confidence=0.5)
        assert route.cascade_models == []
        assert route.cascade_groups == []

    def test_cascade_respects_complexity(self):
        task = Task(complexity=0.1)
        scheduler = AgentScheduler()
        route = scheduler.cascade(task, confidence=0.3)
        assert route.primary_model == "gemma-4"


class TestByzantineConsensus:
    def test_consensus_engine_used(self):
        mock_engine = MagicMock()
        mock_engine.consensus = AsyncMock(return_value=MagicMock(
            consensus_text="consensus result",
            agreement_score=0.85,
            arbitration_needed=False,
        ))
        scheduler = AgentScheduler(consensus_engine=mock_engine)
        outputs = [
            {"text": "result A", "prompt": "test"},
            {"text": "result B", "prompt": "test"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        mock_engine.consensus.assert_called_once_with("test")
        assert result.consensus_text == "consensus result"

    def test_single_output_consensus(self):
        scheduler = AgentScheduler()
        outputs = [{"text": "only answer"}]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert result.consensus_text == "only answer"
        assert result.agreement_score == 1.0
        assert result.arbitration_needed is False

    def test_empty_outputs_consensus(self):
        scheduler = AgentScheduler()
        result = asyncio.run(scheduler.byzantine_consensus([]))
        assert result.consensus_text == ""
        assert result.agreement_score == 0.0
        assert result.arbitration_needed is True

    def test_identical_texts_high_similarity(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": "the quick brown fox"},
            {"text": "the quick brown fox"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert result.agreement_score == 1.0
        assert result.arbitration_needed is False

    def test_different_texts_low_similarity(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": "apples red"},
            {"text": "cars fast"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert result.agreement_score == 0.0
        assert result.arbitration_needed is True

    def test_partial_overlap_similarity(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": "hello world python"},
            {"text": "hello world java"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert 0.0 < result.agreement_score < 1.0

    def test_three_outputs_pairwise(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": "a b c"},
            {"text": "a b d"},
            {"text": "a b e"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert len(result.pairwise_scores) == 3

    def test_consensus_text_from_majority(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": "majority answer"},
            {"text": "majority answer"},
            {"text": "minority answer"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert result.arbitration_needed is False

    def test_model_votes_preserved(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": "a", "model": "m1"},
            {"text": "b", "model": "m2"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert len(result.model_votes) == 2
        assert result.model_votes[0]["model"] == "m1"

    def test_empty_text_in_output(self):
        scheduler = AgentScheduler()
        outputs = [
            {"text": ""},
            {"text": "something"},
        ]
        result = asyncio.run(scheduler.byzantine_consensus(outputs))
        assert result.agreement_score == 0.0


class TestJaccardSimilarity:
    def test_identical_strings(self):
        sim = AgentScheduler._jaccard_similarity("hello world", "hello world")
        assert sim == 1.0

    def test_completely_different(self):
        sim = AgentScheduler._jaccard_similarity("apples", "oranges")
        assert sim == 0.0

    def test_partial_overlap(self):
        sim = AgentScheduler._jaccard_similarity("hello world", "hello python")
        assert sim == pytest.approx(1 / 3, abs=0.01)

    def test_empty_string_a(self):
        sim = AgentScheduler._jaccard_similarity("", "hello")
        assert sim == 0.0

    def test_empty_string_b(self):
        sim = AgentScheduler._jaccard_similarity("hello", "")
        assert sim == 0.0

    def test_case_insensitive(self):
        sim = AgentScheduler._jaccard_similarity("HELLO WORLD", "hello world")
        assert sim == 1.0


class TestAssignmentHistory:
    def test_get_assignment_history_empty(self):
        scheduler = AgentScheduler()
        history = scheduler.get_assignment_history()
        assert history == []

    def test_get_assignment_history_returns_copy(self, simple_task):
        scheduler = AgentScheduler()
        scheduler.schedule(simple_task)
        history = scheduler.get_assignment_history()
        history.clear()
        assert len(scheduler.get_assignment_history()) == 1

    def test_cost_summary_empty(self):
        scheduler = AgentScheduler()
        summary = scheduler.get_cost_summary()
        assert summary["total_assignments"] == 0
        assert summary["total_estimated_cost_usd"] == 0.0

    def test_cost_summary_single(self, simple_task):
        scheduler = AgentScheduler()
        scheduler.schedule(simple_task)
        summary = scheduler.get_cost_summary()
        assert summary["total_assignments"] == 1
        assert summary["by_model"]["gemma-4"] == 1

    def test_cost_summary_multiple(self):
        scheduler = AgentScheduler()
        t1 = Task(complexity=0.2)
        t2 = Task(complexity=0.5)
        scheduler.schedule(t1)
        scheduler.schedule(t2)
        summary = scheduler.get_cost_summary()
        assert summary["total_assignments"] == 2
        assert summary["total_estimated_cost_usd"] == pytest.approx(0.003, abs=1e-4)
        assert len(summary["by_model"]) == 2
