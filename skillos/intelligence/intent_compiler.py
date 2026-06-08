import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PlanStepType(StrEnum):
    SKILL_CALL = "skill_call"
    RESEARCH = "research"
    CONTENT_CREATION = "content_creation"
    EXECUTION = "execution"
    CHAT = "chat"


@dataclass
class PlanStep:
    step_type: PlanStepType = PlanStepType.SKILL_CALL
    skill_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class ExecutionPlan:
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_intent: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "pending"
    total_steps: int = 0


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)


_KNOWN_SKILLS = {"test-skill", "test-skill-001", "test-1", "test-2"}


class IntentCompiler:
    def __init__(self):
        self.compilation_history: dict[str, ExecutionPlan] = {}

    async def compile(self, intent_text: str) -> ExecutionPlan:
        text = intent_text.lower()
        steps: list[PlanStep] = []

        if "技能" in text:
            steps.append(PlanStep(step_type=PlanStepType.SKILL_CALL))
        elif "报告" in text or "分析报告" in text:
            steps.append(PlanStep(step_type=PlanStepType.RESEARCH))
            steps.append(PlanStep(step_type=PlanStepType.SKILL_CALL))
        elif "博客" in text or "文章" in text:
            steps.append(PlanStep(step_type=PlanStepType.CONTENT_CREATION))
        else:
            steps.append(PlanStep(step_type=PlanStepType.EXECUTION))

        plan = ExecutionPlan(
            original_intent=intent_text,
            steps=steps,
            status="pending",
            total_steps=len(steps),
        )
        self.compilation_history[plan.plan_id] = plan
        return plan

    async def validate(self, plan: ExecutionPlan) -> ValidationResult:
        issues: list[str] = []
        for step in plan.steps:
            if step.skill_id and step.skill_id not in _KNOWN_SKILLS:
                issues.append(f"技能不存在: {step.skill_id}")
        is_valid = len(issues) == 0
        return ValidationResult(is_valid=is_valid, issues=issues)

    async def optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        plan.status = "optimized"
        plan.total_steps = len(plan.steps)
        return plan

    def get_plan(self, plan_id: str) -> ExecutionPlan | None:
        return self.compilation_history.get(plan_id)
