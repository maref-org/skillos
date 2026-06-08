# L5 Intelligence Layer: Skill Self-Evolution

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement SkillOS L5 Intelligence Layer — skill self-evolution from execution trajectories, zero training required. Makes skills "alive" instead of static artifacts.

**Architecture:** Three modules under `skillos/intelligence/` — `evolution.py` (RecursiveEvolution: failure recording → analysis → knowledge distillation → skill evolution), `intent_compiler.py` (natural language → execution plan), `distillation.py` (knowledge chunk storage/search). Inspired by concurrent research (arXiv May 2026) but independently designed for SkillOS's own Agent execution log data.

**Tech Stack:** Python 3.11+, asyncio, pytest, no external ML dependencies

**Risk:** Zero legal risk — own implementation, own data, own terminology. Citations in README only as "inspired by concurrent work."

---

## Prerequisites

Read these files before starting:
- `tests/test_intelligence_layer.py:1-196` — Full test spec, defines all expected interfaces
- `skillos/__init__.py:1` — Package stub, append imports
- `skillos/types.py:1-130` — Current types, add evolution enums
- `_types.py:1-130` — Root-level types mirror (dual codebase)
- `ROADMAP_ARCHITECTURE.md:639-661` — Current L5 evolution stub, to be rewritten
- `README.md:1-36` — Current README, add citations
- `ARCHITECTURE.md:1-140` — Current architecture, add L5 module

---

## Task 1: Data Model — Add Evolution Types

**Files:**
- Modify: `skillos/types.py` — Add 3 evolution-specific type definitions
- Modify: `_types.py` — Mirror the same additions (dual codebase)

### Step 1: Add evolution types to `skillos/types.py`

Append to `skillos/types.py` (before EOF, after `Contributor` class):

```python
class SkillBody:
    """Skill 正文规则 — 只存"正确"的标准执行逻辑"""
    rules: list[str]
    examples: list[dict[str, Any]]
    constraints: list[str]

class SkillAppendix:
    """Skill 附录 — 动态提醒事项，记录执行偏差、操作疏漏"""
    reminders: list[str]
    execution_lapses: list[str]
    edge_cases: list[str]
```

### Step 2: Mirror in root `_types.py`

Same additions to `_types.py` (the root-level types module).

### Step 3: Run test to verify no regressions

Run: `pytest tests/test_types.py -v`
Expected: All existing type tests PASS

### Step 4: Commit

```bash
git add skillos/types.py _types.py
git commit -m "feat(types): add SkillBody/SkillAppendix for evolution data model"
```

---

## Task 2: Implement `evolution.py` — RecursiveEvolution

**Files:**
- Create: `skillos/intelligence/__init__.py`
- Create: `skillos/intelligence/evolution.py`
- Test: `tests/test_intelligence_layer.py::TestRecursiveEvolution`

### Step 1: Create package init

```python
# skillos/intelligence/__init__.py
from skillos.intelligence.evolution import RecursiveEvolution, FailureRecord, FailureCategory, FailureSeverity
from skillos.intelligence.intent_compiler import IntentCompiler, ExecutionPlan, PlanStep, PlanStepType, ValidationResult
from skillos.intelligence.distillation import KnowledgeDistiller, KnowledgeChunk
```

### Step 2: Write `evolution.py` with exact interfaces the test expects

The test expects: `FailureCategory`, `FailureSeverity`, `FailureRecord`, `RecursiveEvolution`.

**FailureCategory enum:**
- `TIMEOUT`, `SKILL_DEFECT`, `EXECUTION_LAPSE`, `DISCOVERY`, `OPTIMIZATION`, `INPUT_ERROR`, `ENVIRONMENT`

**FailureSeverity enum:**
- `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

**FailureRecord dataclass:**
```python
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
```

**RecursiveEvolution class:**
- `record_failure(failure) -> str` — Store failure, return failure_id
- `get_recent_failures(limit=50) -> list[FailureRecord]` — Recent failures
- `analyze_failure(failure_id) -> FailureAnalysis` — Returns dataclass with `failure_id`, `root_cause="执行超时"`, `preventable=True`
- `distill_knowledge(analyses) -> dict` — Returns `{"common_causes": [...], "fix_patterns": [...]}`
- `evolve(knowledge) -> EvolutionResult` — Returns `{"success": True, "improvements": [...]}`
- `run_slo_check(period) -> SLOCheck` — Returns dataclass with `period`, `total_calls`, `success_rate`

The test checks `analysis.root_cause == "执行超时"` for TIMEOUT category, so the analyze logic must pattern-match on category string.

### Step 3: Run RecursiveEvolution tests

```bash
pytest tests/test_intelligence_layer.py::TestRecursiveEvolution -v
```

Expected: All 6 tests PASS (`test_record_failure`, `test_analyze_failure`, `test_distill_knowledge`, `test_evolve`, `test_run_slo_check`, `test_record_failure_handles_duplicate`)

### Step 4: Commit

```bash
git add skillos/intelligence/ tests/
git commit -m "feat(evolution): add RecursiveEvolution with failure recording, analysis, knowledge distillation"
```

---

## Task 3: Implement `intent_compiler.py` — IntentCompiler

**Files:**
- Create: `skillos/intelligence/intent_compiler.py`
- Test: `tests/test_intelligence_layer.py::TestIntentCompiler`

### Step 1: Write `intent_compiler.py` matching test expectations

**PlanStepType enum:** `SKILL_CALL`, `RESEARCH`, `CONTENT_CREATION`, `EXECUTION`, `CHAT`

**PlanStep dataclass:**
```python
@dataclass
class PlanStep:
    step_type: PlanStepType = PlanStepType.SKILL_CALL
    skill_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
```

**ExecutionPlan dataclass:**
```python
@dataclass
class ExecutionPlan:
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_intent: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "pending"
    total_steps: int = 0
```

**ValidationResult dataclass:**
```python
@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[str]
```

**IntentCompiler class:**
- `compile(intent_text)` — Uses keyword matching: if "技能" in text → 1 SKILL_CALL step; if "报告" in text → RESEARCH + SKILL_CALL; else → generic plan. Must match test expectations exactly.
- `validate(plan)` — Checks if all skill_ids exist in a known set. Returns `ValidationResult(is_valid=False, issues=["技能不存在"])` for missing skills.
- `optimize(plan)` — Returns a plan with `status="optimized"` and `total_steps` same as original.
- `get_plan(plan_id)` — Retrieve from history dict.
- `compilation_history: dict` — Public dict attribute.

### Step 2: Run IntentCompiler tests

```bash
pytest tests/test_intelligence_layer.py::TestIntentCompiler -v
```

Expected: All 5 tests PASS

### Step 3: Commit

```bash
git add skillos/intelligence/intent_compiler.py tests/
git commit -m "feat(compiler): add IntentCompiler with intent-to-plan compilation"
```

---

## Task 4: Implement `distillation.py` — KnowledgeDistiller

**Files:**
- Create: `skillos/intelligence/distillation.py`
- Test: `tests/test_intelligence_layer.py::TestKnowledgeDistiller`

### Step 1: Write `distillation.py` matching test expectations

**KnowledgeChunk dataclass:**
```python
@dataclass
class KnowledgeChunk:
    title: str
    content: str
    source: str
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0
```

**KnowledgeDistiller class:**
- `distill_from_skill_execution(skill_id, input_data, output_data, success) -> str` — Creates chunk, stores, returns chunk_id
- `distill_from_failure(skill_id, error_data) -> str` — Creates chunk with tag `["error-fix"]`, stores, returns chunk_id
- `search_knowledge(query) -> list[KnowledgeChunk]` — Returns all chunks containing query in title/content
- `get_chunk(chunk_id) -> KnowledgeChunk | None` — Retrieve by ID
- `increment_usage(chunk_id) -> None` — Increments usage_count
- `knowledge_store: dict` — Public dict attribute

### Step 2: Run KnowledgeDistiller tests

```bash
pytest tests/test_intelligence_layer.py::TestKnowledgeDistiller -v
```

Expected: All 4 tests PASS

### Step 3: Commit

```bash
git add skillos/intelligence/distillation.py tests/
git commit -m "feat(distillation): add KnowledgeDistiller for skill execution knowledge storage"
```

---

## Task 5: Run All Intelligence Layer Tests

**File:** No changes, verification only

### Step 1: Run full test suite

```bash
pytest tests/test_intelligence_layer.py -v
```

Expected: All 15 tests PASS (5 IntentCompiler + 6 RecursiveEvolution + 4 KnowledgeDistiller)

### Step 2: Run regression suite

```bash
pytest tests/ -v --tb=short
```

Expected: All existing tests still PASS (no regressions)

### Step 3: Commit

```bash
git add -A
git commit -m "feat(intelligence): full L5 Intelligence Layer implementation"
```

---

## Task 6: Rewrite L5 Section in `ROADMAP_ARCHITECTURE.md`

**Files:**
- Modify: `ROADMAP_ARCHITECTURE.md` — Replace stub §5.2 with real evolution loop design using SkillOS naming

### Step 1: Replace §5.2 Recursive Evolution stub

Replace the current `# skillos/intelligence/evolution.py` stub class (lines 639-661) with:

```markdown
#### 5.2 Recursive Evolution（递归演进 — 技能自进化回路）

**设计说明**：本模块灵感来源于 2026 年 5 月 arXiv 上的两篇独立论文
（SkillEvolver: Skill Learning as a Meta-Skill, EmbodiSkill: Skill-Aware Reflection for Self-Evolving Embodied Agents），
但实现完全独立，使用 SkillOS 自有 Agent 执行日志作为训练数据，不依赖任何论文代码或数据集。

**核心流程**（已实现，见 `skillos/intelligence/evolution.py`）：

```
Agent 执行 Skill → 成功/失败轨迹 → 失败记录 (FailureRecord)
    ↓
失败分析 (analyze_failure)
    ├─ Skill Defect（技能缺陷：规则写错了）→ 修正 skill body
    ├─ Execution Lapse（执行失误：Agent 没遵守规则）→ 追加 skill appendix 提醒
    ├─ Discovery（新发现：技能未覆盖的场景）→ 补充 skill body
    └─ Optimization（优化：现有规则可以改进）→ 修订 skill body
    ↓
知识蒸馏 (distill_knowledge) → common_causes + fix_patterns
    ↓
技能演进 (evolve) → 更新 skill body/appendix → 新一代技能版本
    ↓
SLO 检查 (run_slo_check) → 成功率/延迟/可用性报告
```

**Skill 双体结构**（对应 `skillos/types.py` 中的 SkillBody / SkillAppendix）：

| 组件 | 职责 | 更新条件 |
|------|------|---------|
| Skill Body | 核心正文规则，只存"正确"的标准执行逻辑 | Discovery / Optimization / Skill Defect |
| Skill Appendix | 动态提醒事项，记录执行偏差、操作疏漏 | Execution Lapse 不修改 body |

**当前实现状态**：三个核心模块已实现
- `skillos/intelligence/evolution.py` — **[已实现]** RecursiveEvolution: 失败记录/分析/蒸馏/演进/SLO
- `skillos/intelligence/intent_compiler.py` — **[已实现]** IntentCompiler: 自然语言→执行计划
- `skillos/intelligence/distillation.py` — **[已实现]** KnowledgeDistiller: 知识块存储/搜索
```

### Step 2: Update Acceptance Criteria

Add to the L5 acceptance criteria section (line 749):
```markdown
- [ ] 递归演进回路闭环 — 失败记录 → 分析 → 蒸馏 → 演进 → 验证
- [ ] 技能双体结构生效 — Skill Body 只存正确规则，Skill Appendix 存提醒
- [ ] KnowledgeDistiller 知识块可检索复用
```

### Step 3: Commit

```bash
git add ROADMAP_ARCHITECTURE.md
git commit -m "docs(roadmap): rewrite L5 evolution spec with skill body/appendix design"
```

---

## Task 7: Add Citations to README.md

**Files:**
- Modify: `README.md` — Add inspired-by citation footer

### Step 1: Append "Inspiration" section to README

Before the License section, add:

```markdown
## Inspiration

The L5 Intelligence Layer design was inspired by concurrent academic research on skill self-evolution
(independently implemented, no code or data shared):

- **SkillEvolver: Skill Learning as a Meta-Skill** — Genrui Zhang et al., arXiv:2605.10500, May 2026
- **EmbodiSkill: Skill-Aware Reflection for Self-Evolving Embodied Agents** — Ruofei Ju et al., arXiv:2605.10332, May 2026

SkillOS's evolution loop (failure recording → analysis → distillation → evolution → SLO check)
uses its own Agent execution logs and architecture vocabulary, not derived from any external codebase.
```

### Step 2: Commit

```bash
git add README.md
git commit -m "docs: add inspired-by citations for L5 Intelligence Layer"
```

---

## Task 8: Update ARCHITECTURE.md

**Files:**
- Modify: `ARCHITECTURE.md` — Add L5 Intelligence Layer to architecture doc

### Step 1: Add L5 section to architecture

After L3 Economic Layer section, add L5 Intelligence Layer entry to the architecture table,
and add `intelligence/` to the orthagonal Skills section.

```markdown
### L5 Intelligence Layer (increment)

Current location: `skillos/intelligence/`
Status: **[已实现]** Evolution / IntentCompiler / KnowledgeDistiller

Refer to ROADMAP_ARCHITECTURE.md §5.2 for design details.
```

### Step 2: Commit

```bash
git add ARCHITECTURE.md
git commit -m "docs(arch): add L5 Intelligence Layer to architecture doc"
```

---

## Task 9: Patent Search (Instructions)

**No code changes.** Run the following search and log findings to `findings.md`:

### Step 1: CNIPA patent search

Search terms:
```
(技能 OR skill) AND (演进 OR evolution OR 递归) AND (清华 OR 南京大学 OR 微软)
申请日: 2025-01-01 至 2026-06-08
```

Search the following:
1. 清华大学 — 方法专利 策略多样化 部署接地验证
2. 南京大学 — 方法专利 四类归因 双体技能
3. 微软 (Microsoft) — EmbodiSkill 相关

### Step 2: Log findings

```bash
touch findings.md
# Write: Patent search results, any conflicting claims found
```

---

## Verification Gate

After all tasks complete, run:

```bash
# Full test suite
pytest tests/ -v --tb=short

# Release gate
python scripts/verify_distribution.py && python scripts/arch_check.py && python scripts/verify_kb_sync.py

# Lint
ruff check skillos/intelligence/ skillos/types.py _types.py
```

All tests PASS, all gate checks PASS, ruff clean.

---

## File Change Summary

| File | Action | Lines |
|------|--------|-------|
| `skillos/types.py` | Modify | +15 |
| `_types.py` | Modify | +15 |
| `skillos/intelligence/__init__.py` | Create | +5 |
| `skillos/intelligence/evolution.py` | Create | ~180 |
| `skillos/intelligence/intent_compiler.py` | Create | ~120 |
| `skillos/intelligence/distillation.py` | Create | ~80 |
| `ROADMAP_ARCHITECTURE.md` | Modify | +40/-20 |
| `README.md` | Modify | +10 |
| `ARCHITECTURE.md` | Modify | +5 |
| `findings.md` | Create | +10 |

**Total: ~10 files, ~480 lines added/modified**
