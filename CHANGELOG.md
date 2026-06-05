# Changelog

## [0.4.0-alpha] - 2026-06-05

### Added
- **SessionIsolator**: git worktree sandbox execution isolation with resource limits
- **StatePersistor**: SQLite-based cross-session state persistence with TTL expiry
- **TaskScheduler**: cron expression async task scheduling with persistence
- **WebFetcher**: 4-mode async web content extraction (full/article/links/metadata)
- **RemoteBridge**: remote API bridge control with 5 command handlers
- **MAS integration tests**: 35 test cases across 4 capability suites
- **Engineering infrastructure**: ruff lint, bandit SAST, Makefile automation

### Fixed
- **P0**: `types.py` renamed to `_types.py` — resolved stdlib naming collision that blocked all imports
- **Latent bug**: `_classify_keyword()` call missing `self.` in entry_kernel.py
- **Verification scripts**: correct sys.path resolution for package imports
- **arch_check.py**: .venv/.git exclusion for accurate layer audit

### Changed
- **pyproject.toml**: added ruff/bandit config, `requests` dependency, corrected hatch include
- **Dependencies**: 9 runtime + 7 dev (ruff, bandit, pytest, pytest-cov, pytest-asyncio)

---

## [0.3.0] - 2026-05-25

### Added
- EntryKernel: 20/80 human-AI routing with intent classification
- AgentScheduler: 4-tier model routing with Byzantine consensus
- SkillKernel: skill distillation, NFT minting, toolchain assembly
- SessionManager: session lifecycle (CRUD + 4-state machine)
- DistributionEngine: 5/25/70 economic model with dynamic weights
- Protocol clients: Registry, Matcher, Settlement, Identity (4 clients)
- 55+ skill plugins covering AI workflows, content creation, dev tools

### Infrastructure
- AGPL-3.0 licensed open source release
- Hatchling build system with editable install
- 529 test suite (100% pass rate)
- 31 MAS capability declarations
