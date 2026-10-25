# Changelog

## [Unreleased] - 2026-10-25

### Fixed
- **发布门禁统一入口** — 新增 `scripts/release_gate.sh`，本地 `make gate` 与
  CI/release 流水线执行同一套 11 步检查；`release.yml` 通过可复用
  `release-gate.yml` 强制门禁，tag 不再绕过测试。
- **CI 红灯** — 修复 `F821`（skillos-contrib 缺 `import os`）、统一 ruff 作用域、
  `mypy` 54 处类型错误归零；`ci.yml` 的 lint/security 与门禁口径对齐。
- **治理扫描空转** — `sanitize-for-push.sh` 修正 `grep` 缺少 `-E` 的失效匹配，
  改为 `git grep` 扫描全部已跟踪文件（含 skills/、skillos-contrib/、audit_logs/），
  并新增负向测试 `tests/test_sanitize_script.py` 保证门禁真的会失败。
- **审计链跨重启** — 无 `SKILLOS_AUDIT_SECRET` 时生成持久化
  `audit_logs/.audit_secret`（0600），M1 仅校验当日链；M0 运行态检查改为
  `SKILLOS_META_ENFORCE_RUNTIME=1` 显式开启。
- **依赖漏洞** — `cryptography>=50.0.0`、`gitpython>=3.2.1`、`litellm>=1.96.2`，
  补齐 dev 依赖（mypy/pip-audit/pre-commit/OpenTelemetry）；`uv.lock` 重建为独立 lock。
- **容器入口** — 新增 `skillos/__main__.py`，`python -m skillos` 可启动并响应
  `/health`；Dockerfile 安装 `.[web]`；新增 `.dockerignore`。
- **制品完整性** — wheel 打包 `migrations/` 与 `alembic.ini`；安装元数据与源码版本对齐。
- **测试隔离** — `TaskScheduler` 默认配置路径改为运行时解析，测试不再写
  `data/scheduled_tasks.json`；`test_governance_layer.py` 显式声明 skip 原因。
- **仓库卫生** — `audit_logs/` 与 `.DS_Store` 移出索引，`coverage.json`/`.registry/`
  加入忽略。
- **CI 恢复绿灯** — 用公开文件替换 `docs/CONTRIBUTING.md`、`docs/CROSS_PROJECT.md`、
  `docs/api` 三个指向私有知识库的符号链接；sanitize 新增绝对路径符号链接检测；
  `verify_kb_version_sync` 仅校验活跃文档并忽略依赖版本号。
- **工作流修复** — TruffleHog action 改为 `@main`；DAST 目标改为 `/health` 并关闭
  issue 写入；Meta-Audit 将空审计目录视为无事件；k6 改用 runner 本机执行。
  重新启用因不活跃被禁用的 CodeQL / Security Scan / Meta-Audit / Load Test。

## [Unreleased] - 2026-10-24

### Changed
- **CSWDP 生存保障金拆分为地板/天花板两账户** — `SurvivalFundRecord` 新增
  `unconditional_amount` / `performance_bonus` / `accounts` / `floor_is_unconditional`；
  `SurvivalFundCalculator` 保证无条件基础不参与任何 clamp / min / 条件分支，
  绩效奖金上限 = 基础 × (cap_multiplier − 1)；`calculate()` 新增
  `include_performance_bonus` 开关；API 请求体同步新增该字段。设计见
  `docs/plans/2026-10-24-cswdp-unconditional-floor-split.md`。+8 测试。
  旧公式（base + bonus 混算）标注为历史记录，不再作为语义依据。

### Fixed
- **小费出款链路补齐** — `PayoutService.generate_for_contract()` 此前只生成
  contractor / skill_author / platform 三类指令，`tips` 表记账的小费
  （`source=tip`）从不进入出款 manifest，导致到账率被高估。现按小费分配明细
  生成独立指令；防超发校验拆为「结算 ≤ 契约价」与「小费 ≤ 记账小费」两条。
- **manifest 增加 reconciliation 块** — 显式列出 `ecosystem_pending_allocation`，
  避免 25% 生态基金因无收款主体而被误读为已出款。


## [Unreleased] - 2026-08-01

### Added
- **Outcome Contract Loop 成果契约闭环 M1** — 四边生态（需求方/Agent 构建者/技能作者/验证节点）+ 按成果付费基础层
  - `skillos/collaboration/`（新建，激活预留测试桩）: `ByzantineConsensus`（拜占庭共识，门限 (2n)//3+1）+ `TrustReputationEngine`（信誉分 = 执行 0.4 + 评价 0.3 + 治理 0.2 + 参与 0.1）+ 16 tests
  - `skillos/market/outcome_contracts.py`（新建）: `OutcomeContractService` — 需求规则拆解（内容 IP 垂直场景，LLM 抽象降级）、三方案报价（A 稳妥/ B 均衡/ C 冲刺，成功率×价格×工期）、契约状态机（draft→open→in_progress→submitted→work_completed→paid + disputed/cancelled）、超预期小费（10-20%，项目长 50% + 技能作者 50%）、履约保证金（10%）、5/25/70 结算复用 + 20 tests
  - `db/models.py`: 新增 5 模型（ReputationModel/OutcomeContractModel/ServiceTeamModel/ServiceTeamMemberModel/TipModel）+ Alembic migration 005（幂等 + server_default）
- **Outcome Contract Loop 成果契约闭环 M2** — `web_api/outcome.py`（新建）API 层，Ed25519 签名鉴权（复用 MessageSigner）
  - `POST /outcome/contracts`（提需求 + 三方案报价，requester 签名强制身份）
  - `POST /outcome/contracts/{id}/select-tier`（选档签约）/ `sign`（项目长开工）/ `submit-delivery`（交付）/ `confirm`（验收，含小费选项）/ `tip`（超预期小费）
  - `GET /outcome/contracts/{id}`（契约详情/证据链 + 小费记录，只读）/ `GET /outcome/reputation/{entity_id}`（信誉分查询，只读）
  - +19 API 测试（全生命周期 / 争议 / 权限隔离 / 签名鉴权拒绝路径）
- **Outcome Contract Loop 成果契约闭环 M3** — 五层多方法律风险承担（风控降本）落地
  - **L2 资金保障**: `outcome_contracts.deposit_status`（held→released/forfeited）+ migration 006；结算释放保证金，仲裁违约扣留保证金，平台零垫付
  - **L3 证据/验收层**: `submit_delivery` 强制过 `HallucinationDetector`（风险 HIGH/CRITICAL 拒绝提交），存 `evidence_hash`（SHA256，不落原文）+ `evidence_risk`，审计日志存证不可抵赖
  - **L4 仲裁层**: `arbitrate()` disputed → `ByzantineConsensus` 多方投票（approve 达门限→work_completed+释放保证金 / reject 达门限→cancelled+扣保证金 / 未达门限→pending 外部仲裁）
  - API: `POST /outcome/contracts/{id}/submit-delivery` 支持 `evidence_text` + `POST /outcome/contracts/{id}/arbitrate`（签名）+ 26 新测试
- **Outcome Contract Loop 成果契约闭环 M4** — 开放外部 Agent 构建者当项目长（Q2 三方生态）+ 首个真实需求方跑通（Go/No-Go）
  - `web_api/agent.py` 新增 MCP 风格端点：`GET /agent/list_open_contracts`（浏览可承接 open 契约，免费只读）/ `POST /agent/accept_contract`（外部 Agent 承接当项目长，contractor 强制签名身份，红线 §8.2）/ `GET /agent/list_my_contracts`（查询自己承接的契约）
  - `OutcomeContractService` 新增 `list_open` / `list_by_contractor`
  - 首个真实需求方端到端验收（`tests/test_outcome_go_no_go.py`）：需求方提自然语言需求→三方案报价→选档→外部 Agent 浏览承接→组队→交付（L3 合规）→验收+小费→结算→保证金释放 = **Go**；争议仲裁路径（reject→扣保证金）也闭环 + 6 测试
- **Outcome Contract Loop 成果契约闭环 M5** — 真实商业验证（持牌支付桥接 + 外部 Agent 接入演示 + 垂直场景内测）
  - `db/models.py`: 新增 `PayoutInstructionModel`（id/contract_id/payee_id/role/amount/currency/source/status/external_ref/created_at/updated_at）+ migration 007（幂等 + 2 索引）
  - `skillos/market/payouts.py`（新建）: `PayoutService` — `generate_for_contract`（按 contract_id 幂等去重，项目长 70% + 技能作者按 share_ratio + 平台 5%）、`export_manifest` / `export_period_manifest`（记账指令导出，注明明示"不托管资金"）、`mark_executed`（写 external_ref 标记已执行）、`list_by_payee`
  - API: `GET /outcome/payouts/{contract_id}`（出款指令 manifest 导出，只读；契约不存在 404）
  - `scripts/external_agent_demo.py`（新建）: 外部 Agent 接入演示，垂直场景「内容 IP 代运营」——企业主提需求→三方案报价→选档→外部 Agent 浏览承接→组队→交付→验收+小费→结算→出款指令导出 = **GO**（`make audit` 1308 passed, 1 skipped, coverage 88.66%）

- **Outcome Contract Loop 成果契约闭环 M6** — 持牌支付 manifest 对接 + 真实外部 Agent 接入 + 垂直场景上线内测
  - `skillos/market/payments/`（新建）: `base.py`（`PaymentProvider` 协议 + `get_provider()` 工厂，无 key 一律降级 sandbox）+ `sandbox.py`（本地模拟持牌支付）+ `alipay.py`（RSA2 签名，`alipay.fund.trans.uni.transfer` 沙箱）+ `wechat.py`（v3 HMAC-SHA256 签名，转账沙箱）+ `submit_contract_payout()`（出款 → 提交 → 回写 external_ref）
  - `web_api/payments.py`（新建）: `GET /payments/providers` / `POST /payments/webhooks/{provider}`（验签 → mark_executed）/ `POST /payments/contracts/{id}/submit` + 挂载到 `/api/v1`
  - `MessageSigner.sign_headers_http()`: X-Public-Key base64url 编码（HTTP 头禁止换行），`verify()` 兼容解码
  - `scripts/run_server.py`（真实 uvicorn 服务）+ `scripts/agent_http_client.py`（外部 Agent HTTP 客户端）+ `external_agent_demo.py --real-server`（真实 HTTP 端到端 GO）
  - `skillos/scenarios/ip_operations.py`（内容 IP 代运营场景包：内容代运营/短视频矩阵/知识付费专栏 3 模板）+ `scripts/ip_operations_trial.py`（一键内测 CLI，内置/真实双模式）
  - +38 测试；`make audit` 全绿 — 1346 passed, 1 skipped, coverage 88.77%

### Notes
- 维持红线 §9「不托管真实资金」：结算停留记账层，法币支付由下游持牌平台承接
- 维持红线 §8.2「AI 不独立缔约」：契约方强制为已注册签名身份，未注册签名 403 / 缺失签名 401
- M5 出款指令仅作持牌支付桥接的记账输入，不触碰真实资金（红线 §9）

## [0.6.0-beta] - 2026-07-30

### Added
- **L3 Skill Market MVP** (`skillos/market/`): 3 modules + 36 tests
  - `SkillRegistry`: skill listing, search, version management, deprecation, reviews, quality scoring
  - `PricingEngine`: dynamic pricing with supply/demand factor + quality score + optimal price
  - `SettlementEngine`: 5/25/70 settlement with per-listing and per-period settlement + earnings summary
  - FastAPI router: `POST /market/register`, `GET /market/search`, `POST /market/settle`, etc.
  - Alembic migration 003: 3 new tables (skill_listings, skill_reviews, settlements)
  - NegMarket integration: auto-register anti-pattern skills on the market
- **Phase A: Stability cleanup** — flaky test fix, SKILLOS_AUDIT_SECRET config, ruff 0 errors, mypy 0 errors
- **Phase B: Production hardening**
  - `scripts/load-test.js` — k6 3-scenario load test (baseline/peak/soak)
  - `.github/workflows/codeql.yml` — CodeQL Python analysis (weekly + PR)
  - `.semgrep/rules/python-security.yaml` — 4 Semgrep SAST rules
  - `scripts/chaos_test.py` — 3 chaos scenarios (process_kill/network_disconnect/resource_exhaustion)
  - `.github/workflows/load-test.yml` — k6 CI integration
  - PostgreSQL optional dep: `pip install skillos[postgres]`
  - SBOM generation via `anchore/sbom-action` in release-gate.yml
  - Cosign container signing in release.yml
- **Phase A docs**: `docs/spof.md`, `docs/capacity-plan.md`
- `db_session` fixture in `tests/conftest.py` for shared test DB access

### Fixed
- **Flaky test**: `test_concurrent_create` — added `_write_lock` to `FeatureFlagManager` (thread-safe serialization)
- **Mypy**: 27 errors → 0 errors across 7 files (audit.py, web_fetch.py, logging_config.py, session_manager.py, process_sandbox.py, identity_client.py, skill_importer.py, negmarket/storage.py)
- **Ruff**: 0 errors maintained

### Changed
- **Version**: 0.5.0-beta → 0.6.0-beta (pyproject.toml, version.py, app.py, README.md)
- **ARCHITECTURE.md**: L3 updated to include Skill Market MVP
- **Dependencies**: (postgres) optional group added (psycopg2-binary)
- **Test suite**: 1148 → **1184 passed**, 2 skipped, 0 failed

## [0.5.0-beta] - 2026-07-02

### Added
- **Phase 5: Intelligence Evolution** (L5 RecursiveEvolution with self-evolution loop)
- **Competitive intelligence automation pipeline** (`skillos/scripts/competitive_intel.py`)
- **KB-Code version sync CI check** (gate before merge)
- **Cross-platform skill importer** (Anthropic/YAML/Raw JSON)
- **LiteLLM-based intent classifier** with keyword fallback
- **SLO/SLI definition** with error budget calculation
- **Real MCP client connector** (replaced stub URI)
- **Pre-commit hook**: Athena T3 leak prevention

### Fixed
- **IdentityClient**: Ed25519 real cryptography + challenge-response authentication
- **Persistent storage**: SQLAlchemy 2.0 + PostgreSQL/SQLite + Alembic migrations
- **Audit logging**: HMAC-SHA256 append-only chain
- **HTTPS enforcement**: default HTTPS with `--insecure` flag for dev
- **API key**: environment variable `SKILLOS_API_KEY`, no hardcoding
- **Sandbox isolation**: process-level sandbox with input validation, keyword filtering, subprocess timeout
- **Observability**: Prometheus RED metrics, OpenTelemetry, structured JSON logging
- **SLO/SLI**: P99 < 500ms, availability 99.9%

### Changed
- **Dual-package eliminated**: All flat packages (kernel/, protocol/, distribution/, negmarket/) consolidated into `skillos/` as the sole source
- **Version unified**: v0.5.0-beta across pyproject.toml, README.md, ARCHITECTURE.md, version.py
- **Makefile**: targets updated for skillos/ (post-consolidation)
- **Release gate**: 15-item custom gate with updated skillos/ paths
- **Test suite**: 758 passing (pre-existing e2e/integration timeout excluded)

### Infrastructure
- AGPL-3.0 licensed open source release
- Hatchling build system with editable install
- 11 CI workflows (lint, test, security, DAST, release-gate, exfiltration check, etc.)
- Pre-commit hooks: 9 hooks including custom T3 leak prevention
- SECURITY.md: skillos-specific (replaced MAREF copy)

## [0.4.0-alpha] - 2026-06-05

### Added
- **NegMarket MVP**: 7-module negative sample market (`skillos/negmarket/`)
  - 4-step desensitization pipeline (PII replace → ZK → anti-pattern → dynamic mask)
  - AES-256-GCM encrypted SQLite storage via `cryptography`
  - Anti-pattern Skill generator with risk-level warnings
  - HMAC-SHA256 simulated ZK verifier
  - Optional FastAPI adapter (`pip install skillos[web]`)
  - 5/25/70 revenue integration in DistributionEngine
  - 42 test cases (100% core module coverage)
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
- **pyproject.toml**: added ruff/bandit config, `cryptography` dep, `web` extras group, hatch include `negmarket`
- **Dependencies**: 10 runtime + 7 dev + 2 web extras (fastapi, uvicorn)

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
