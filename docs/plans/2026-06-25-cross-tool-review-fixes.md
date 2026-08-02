# Cross-Tool Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 2 blocking + 7 suggested issues identified in Layer 2 cross-tool review

**Architecture:** 9 independent fixes across 6 files — scripts, CI config, pyproject.toml, gitignore, and 3 skillos modules. No shared state or sequential dependencies between tasks.

**Tech Stack:** Python 3.11+, GitHub Actions YAML

---

## Task 1: Fix `verify_distribution.py` import path (B-1)

**Files:**
- Modify: `scripts/verify_distribution.py:11`

**Current code:**
```python
from skillos._types import SkillCall
```

**Expected:**
```python
from skillos.types import SkillCall
```

**Step 1: Verify the module exists**
```bash
python3 -c "from skillos.types import SkillCall; print('OK')"
```

**Step 2: Fix the import**
Change `skillos._types` → `skillos.types` in the import line.

**Step 3: Verify the script runs**
```bash
python3 scripts/verify_distribution.py
```

---

## Task 2: Fix CI workflow paths (B-2)

**Files:**
- Modify: `.github/workflows/release-gate.yml:21,31,63`

**Changes needed:**
1. `ruff check kernel/ protocol/ distribution/` → `ruff check skillos/ scripts/`
2. `pytest tests/ --cov=kernel --cov=distribution --cov=protocol` → `pytest tests/ --cov=skillos`
3. `bandit -r kernel/ protocol/ distribution/` → `bandit -r skillos/`

**Step 1: Edit release-gate.yml line 21**
Change ruff check paths from flat directories to `skillos/ scripts/`

**Step 2: Edit release-gate.yml line 26**
Change `--cov=kernel --cov=distribution --cov=protocol` to `--cov=skillos`

**Step 3: Edit release-gate.yml line 31**
Change `bandit -r kernel/ protocol/ distribution/` to `bandit -r skillos/`

**Step 4: Verify YAML syntax**
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release-gate.yml')); print('YAML OK')"
```

---

## Task 3: Fix coverage source paths in pyproject.toml (S-1)

**Files:**
- Modify: `pyproject.toml:41`

**Current:**
```toml
source = ["kernel", "distribution", "protocol", "skillos", "negmarket"]
```

**Expected:**
```toml
source = ["skillos"]
```

**Step 1: Edit pyproject.toml**
Replace the source list.

**Step 2: Verify**
```bash
python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('TOML OK')"
```

---

## Task 4: Fix `_success_counter` in evolution.py (S-2)

**Files:**
- Modify: `skillos/intelligence/evolution.py:65-69`

**Current code:**
```python
async def record_failure(self, failure: FailureRecord) -> str:
    self._failures[failure.failure_id] = failure
    self._call_counter += 1
    return failure.failure_id
```

The issue is `_success_counter` is never incremented. However, we need a `record_success` method or increment it somewhere. Let me check what makes sense.

Looking at the class: `_call_counter` increments on failure, but there's no `record_success` method. We should add one and ensure `_success_counter` is incremented when appropriate. Actually, looking at the code more carefully:

- `_call_counter` increments in `record_failure` only — this seems like a bug where `_call_counter` should be incremented for ALL calls, not just failures
- `_success_counter` is never set to anything > 0

**Fix plan:**
1. Rename `_call_counter` to `_total_calls` for clarity
2. Increment `_total_calls` in both success and failure paths
3. Add a `record_success()` method or change `record_failure` to not conflate total count with failures

**Minimal fix:**
Add a `record_success` method that increments both `_call_counter` and `_success_counter`:
```python
async def record_success(self) -> str:
    self._call_counter += 1
    self._success_counter += 1
    return "success"
```

Also fix `record_failure` to only count failure, not total call (or rename total):
Actually, simplest: rename `_call_counter` → `_total_calls`, and add a separate `_failure_counter`, then `_success_counter = _total_calls - _failure_counter`.

**Simplest minimal fix:**
Increment `_call_counter` in both places — add a `record_success`:
```python
async def record_success(self) -> str:
    self._call_counter += 1
    self._success_counter += 1
    return "success"
```

And fix `record_failure` to NOT increment `_call_counter` (or rename it). Actually, the simplest approach: just change `record_failure` to not increment `_call_counter`, and add `record_success` that increments both counters.

Wait, it's cleaner to:
1. Keep `_call_counter` as total calls 
2. Increment `_call_counter` in `record_failure` AND `record_success`
3. Increment `_success_counter` only in `record_success`

So:
```python
async def record_failure(self, failure: FailureRecord) -> str:
    self._failures[failure.failure_id] = failure
    self._call_counter += 1
    return failure.failure_id

async def record_success(self) -> str:
    self._call_counter += 1
    self._success_counter += 1
    return "success"
```

This way `_call_counter` always equals total calls, `_success_counter` = successes, and `run_slo_check` works correctly.

---

## Task 5: Add backup files to .gitignore (S-3)

**Files:**
- Modify: `.gitignore`

**Add after existing Trae AI config block:**
```
# Backup files
*.bak
*.bak.*
```

**Step 1: Edit .gitignore**
Append the backup file pattern.

**Step 2: Verify git ignores it**
```bash
git status opencode.jsonc.bak.* 2>&1 | head -3
```

---

## Task 6: Add mypy to dev dependencies (S-4)

**Files:**
- Modify: `pyproject.toml:26-32`

**Current:**
```toml
dev = [
    "pytest>=8.0",
    "pytest-cov>=6.0",
    "pytest-asyncio>=0.23",
    "bandit>=1.9.4",
    "ruff>=0.15.16",
]
```

**Expected:** Append `"mypy>=1.0"` to the list.

**Step 1: Edit pyproject.toml**
Add `"mypy>=1.0"` to dev dependencies.

**Step 2: Verify TOML parses**
```bash
python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('TOML OK')"
```

---

## Task 7: Fix `search_sessions()` to not hardcode ACTIVE (S-5)

**Files:**
- Modify: `skillos/kernel/session_manager.py:275-290`

**Current behavior:** `search_sessions(user_id, query)` only searches `SessionStatus.ACTIVE` sessions.
**Expected behavior:** Search all sessions for the given user, optionally filterable.

**Minimal fix:** Remove the status filter from the `list_sessions` call:

```python
def search_sessions(self, user_id: str, query: str) -> list[Session]:
    """搜索会话（基于 metadata）"""
    sessions = self.list_sessions(user_id=user_id)  # remove status filter
    ...
```

If we want backward compat, add a `status` parameter defaulting to `None`.

---

## Task 8: Simplify `_find_majority_index` in agent_scheduler.py (S-6)

**Files:**
- Modify: `skillos/kernel/agent_scheduler.py:243-253`

**Current code:** Nested loop mapping pairwise index back to original index — fragile and unclear.

**Fix:** Use `itertools.combinations` to build explicit pair mapping, making the logic self-documenting:

```python
@staticmethod
def _find_majority_index(scores: list[float], n: int) -> int:
    if not scores or n <= 1:
        return 0
    # Build (i, j) pairs from combinations
    from itertools import combinations
    pairs = list(combinations(range(n), 2))
    if not pairs:
        return 0
    # Find the pair with highest similarity
    best_idx = scores.index(max(scores))
    # The first element of that pair is the majority choice
    return pairs[best_idx][0]
```

---

## Task 9: Add HTTPS docstring to negmarket API (S-7)

**Files:**
- Modify: `skillos/negmarket/api.py:41`

**Add a docstring warning:**
```python
@router.post("/upload")
async def upload_negative_sample(
    raw_text: str = Body(..., min_length=1, max_length=100000),
    category: str = Body("general"),
    contributor_id: str = Body(...),
    contributor_secret: str = Body(...),
    storage: StorageBackend = Depends(get_storage),
    pipeline: DesensitizationPipeline = Depends(get_pipeline),
):
    """上传负样本。
    
    Note: contributor_secret 以明文传输，生产环境必须使用 HTTPS。
    """
```

---

## Verification Plan

After all tasks complete, run:

```bash
# 1. Distribution script
python3 scripts/verify_distribution.py

# 2. TOML validity
python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('TOML OK')"

# 3. YAML validity
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release-gate.yml')); print('YAML OK')"

# 4. Gitignore
git status --short

# 5. Core tests
python3 -m pytest tests/test_agent_scheduler.py tests/test_session_manager.py -q --tb=short

# 6. Verify distribution
python3 scripts/verify_distribution.py && python3 scripts/arch_check.py && python3 scripts/verify_kb_sync.py
```
