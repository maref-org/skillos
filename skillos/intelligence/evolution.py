import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FailureCategory(StrEnum):
    TIMEOUT = "timeout"
    SKILL_DEFECT = "skill_defect"
    EXECUTION_LAPSE = "execution_lapse"
    DISCOVERY = "discovery"
    OPTIMIZATION = "optimization"
    INPUT_ERROR = "input_error"
    ENVIRONMENT = "environment"


class FailureSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FailureRecord:
    skill_id: str
    call_id: str
    severity: FailureSeverity
    category: FailureCategory
    error_message: str
    stack_trace: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    failure_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


@dataclass
class FailureAnalysis:
    failure_id: str
    root_cause: str
    preventable: bool


@dataclass
class EvolutionResult:
    success: bool
    improvements: list[str]


@dataclass
class SLOCheck:
    period: str
    total_calls: int
    success_rate: float


class RecursiveEvolution:
    def __init__(self):
        self._failures: dict[str, FailureRecord] = {}
        self._analyses: dict[str, FailureAnalysis] = {}
        self._call_counter: int = 0
        self._success_counter: int = 0

    async def record_failure(self, failure: FailureRecord) -> str:
        self._failures[failure.failure_id] = failure
        self._call_counter += 1
        return failure.failure_id

    def get_recent_failures(self, limit: int = 50) -> list[FailureRecord]:
        records = list(self._failures.values())
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records[:limit]

    async def analyze_failure(self, failure_id: str) -> FailureAnalysis:
        failure = self._failures.get(failure_id)
        if failure is None:
            return FailureAnalysis(failure_id=failure_id, root_cause="未知错误", preventable=False)

        cause_map = {
            FailureCategory.TIMEOUT: "执行超时",
            FailureCategory.SKILL_DEFECT: "技能缺陷",
            FailureCategory.EXECUTION_LAPSE: "执行失误",
            FailureCategory.DISCOVERY: "新场景发现",
            FailureCategory.OPTIMIZATION: "优化机会",
            FailureCategory.INPUT_ERROR: "输入错误",
            FailureCategory.ENVIRONMENT: "环境异常",
        }
        root_cause = cause_map.get(failure.category, "未分类错误")
        preventable = failure.severity in (FailureSeverity.HIGH, FailureSeverity.CRITICAL)

        analysis = FailureAnalysis(
            failure_id=failure_id,
            root_cause=root_cause,
            preventable=preventable,
        )
        self._analyses[failure_id] = analysis
        return analysis

    async def distill_knowledge(self, analyses: list[FailureAnalysis]) -> dict[str, Any]:
        common_causes: dict[str, int] = {}
        fix_patterns: list[str] = []
        for a in analyses:
            common_causes[a.root_cause] = common_causes.get(a.root_cause, 0) + 1
            if a.preventable:
                fix_patterns.append(f"检查并修复: {a.root_cause}")

        return {
            "common_causes": [{"cause": k, "count": v} for k, v in sorted(common_causes.items(), key=lambda x: -x[1])],
            "fix_patterns": fix_patterns,
        }

    async def evolve(self, knowledge: dict[str, Any]) -> EvolutionResult:
        improvements: list[str] = []
        for fix in knowledge.get("fix_patterns", []):
            improvements.append(fix)
        if not improvements:
            improvements.append("无需修复")

        return EvolutionResult(success=True, improvements=improvements)

    async def run_slo_check(self, period: str = "24h") -> SLOCheck:
        total = self._call_counter if self._call_counter > 0 else 1
        success_rate = self._success_counter / total if total > 0 else 1.0
        return SLOCheck(period=period, total_calls=total, success_rate=round(success_rate, 4))
