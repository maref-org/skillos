"""Tests for skillos.intelligence — Intelligence Layer (L5)

覆盖:
- IntentCompiler: 意图编译、验证、优化
- RecursiveEvolution: 失败分析、知识蒸馏、SLO检查
- KnowledgeDistiller: 知识存储、搜索
"""

import pytest

pytest.importorskip("skillos.intelligence")

from skillos.intelligence.intent_compiler import (
    IntentCompiler,
    ExecutionPlan,
    ValidationResult,
    PlanStep,
    PlanStepType,
)
from skillos.intelligence.evolution import (
    RecursiveEvolution,
    FailureRecord,
    FailureCategory,
    FailureSeverity,
)
from skillos.intelligence.distillation import KnowledgeDistiller, KnowledgeChunk


class TestIntentCompiler:
    @pytest.fixture
    def compiler(self):
        return IntentCompiler()

    @pytest.mark.asyncio
    async def test_compile_basic_intent(self, compiler):
        plan = await compiler.compile("帮我写一篇博客文章")
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) > 0
        assert plan.status in ["pending", "Pending"]

    @pytest.mark.asyncio
    async def test_compile_with_intent_detection(self, compiler):
        plan = await compiler.compile("运行技能处理数据")
        assert len(plan.steps) == 1
        assert plan.steps[0].step_type == PlanStepType.SKILL_CALL

    @pytest.mark.asyncio
    async def test_compile_content_creation(self, compiler):
        plan = await compiler.compile("生成一份分析报告")
        assert len(plan.steps) == 2
        assert plan.steps[0].step_type == PlanStepType.RESEARCH
        assert plan.steps[1].step_type == PlanStepType.SKILL_CALL

    @pytest.mark.asyncio
    async def test_validate_valid_plan(self, compiler):
        plan = await compiler.compile("执行测试任务")
        result = await compiler.validate(plan)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_plan_with_missing_skill(self, compiler):
        plan = ExecutionPlan(
            original_intent="test",
            steps=[PlanStep(skill_id="nonexistent_skill")],
        )
        result = await compiler.validate(plan)
        assert result.is_valid is False
        assert any("技能不存在" in i for i in result.issues)

    @pytest.mark.asyncio
    async def test_optimize_plan(self, compiler):
        plan = await compiler.compile("帮我执行任务")
        original_steps = len(plan.steps)
        optimized = await compiler.optimize(plan)
        assert optimized.status == "optimized"
        assert optimized.total_steps == original_steps  # 保持步骤数

    def test_get_plan_history(self, compiler):
        plan = ExecutionPlan(plan_id="test-plan")
        compiler.compilation_history["test-plan"] = plan
        retrieved = compiler.get_plan("test-plan")
        assert retrieved is not None
        assert retrieved.plan_id == "test-plan"


class TestRecursiveEvolution:
    @pytest.fixture
    def evolution(self):
        return RecursiveEvolution()

    @pytest.fixture
    def sample_failure(self):
        return FailureRecord(
            skill_id="test-skill-001",
            call_id="call-001",
            severity=FailureSeverity.HIGH,
            category=FailureCategory.TIMEOUT,
            error_message="Request timed out after 30s",
            stack_trace="Traceback...",
            input_data={"param": "value"},
        )

    @pytest.mark.asyncio
    async def test_record_failure(self, evolution, sample_failure):
        failure_id = await evolution.record_failure(sample_failure)
        assert failure_id
        recent = evolution.get_recent_failures()
        assert len(recent) == 1
        assert recent[0].failure_id == sample_failure.failure_id

    @pytest.mark.asyncio
    async def test_analyze_failure(self, evolution, sample_failure):
        await evolution.record_failure(sample_failure)
        analysis = await evolution.analyze_failure(sample_failure.failure_id)
        assert analysis.failure_id == sample_failure.failure_id
        assert analysis.root_cause == "执行超时"
        assert analysis.preventable is True

    @pytest.mark.asyncio
    async def test_distill_knowledge(self, evolution, sample_failure):
        await evolution.record_failure(sample_failure)
        analysis = await evolution.analyze_failure(sample_failure.failure_id)
        knowledge = await evolution.distill_knowledge([analysis])
        assert "common_causes" in knowledge
        assert "fix_patterns" in knowledge

    @pytest.mark.asyncio
    async def test_evolve(self, evolution, sample_failure):
        await evolution.record_failure(sample_failure)
        analysis = await evolution.analyze_failure(sample_failure.failure_id)
        knowledge = await evolution.distill_knowledge([analysis])
        result = await evolution.evolve(knowledge)
        assert result.success is True
        assert len(result.improvements) > 0

    @pytest.mark.asyncio
    async def test_run_slo_check(self, evolution):
        check = await evolution.run_slo_check("24h")
        assert check.period == "24h"
        assert check.total_calls >= 1
        assert check.success_rate >= 0.0


class TestKnowledgeDistiller:
    @pytest.fixture
    def distiller(self):
        return KnowledgeDistiller()

    @pytest.mark.asyncio
    async def test_distill_from_skill_execution(self, distiller):
        chunk_id = await distiller.distill_from_skill_execution(
            skill_id="test-skill",
            input_data={"x": 1},
            output_data={"y": 2},
            success=True,
        )
        assert chunk_id
        chunk = distiller.get_chunk(chunk_id)
        assert chunk is not None
        assert chunk.source == "test-skill"

    @pytest.mark.asyncio
    async def test_distill_from_failure(self, distiller):
        chunk_id = await distiller.distill_from_failure(
            skill_id="test-skill",
            error_data={"error": "Timeout", "cause": "Network"},
        )
        assert chunk_id
        chunk = distiller.get_chunk(chunk_id)
        assert chunk is not None
        assert "error-fix" in chunk.tags

    @pytest.mark.asyncio
    async def test_search_knowledge(self, distiller):
        await distiller.distill_from_skill_execution(
            skill_id="test-1",
            input_data={"a": 1},
            output_data={"b": 2},
            success=True,
        )
        await distiller.distill_from_skill_execution(
            skill_id="test-2",
            input_data={"c": 3},
            output_data={"d": 4},
            success=True,
        )
        results = await distiller.search_knowledge("执行模式")
        assert len(results) >= 1

    def test_increment_usage(self, distiller):
        chunk = KnowledgeChunk(title="test", content="test", source="test")
        distiller.knowledge_store[chunk.chunk_id] = chunk
        distiller.increment_usage(chunk.chunk_id)
        updated = distiller.get_chunk(chunk.chunk_id)
        assert updated.usage_count == 1
