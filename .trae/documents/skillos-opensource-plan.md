# SkillOS 开源独立化实施计划

## 1. 摘要 (Summary)

将 `/Volumes/1TB-M2/public/skillos` 从 OpenHuman/OpenClaw 生态中完全解耦，成为独立开源项目。核心目标：
- **文档隔离**：建立独立文档库（位于 OPC 工作区），通过软链接引用 OpenHuman 知识库
- **商业脱敏**：移除所有 Athena/OpenClaw/OpenHuman 商业敏感引用
- **工程独立**：建立独立 CI/CD、版本发布流程、PyPI 发布能力
- **Skills 拆分**：将通用 skills 保留为核心资产，项目特定 skills 迁移到独立仓库

## 2. 现状分析 (Current State)

### 2.1 代码结构
```
skillos/
├── kernel/              # EntryKernel, SkillKernel, AgentScheduler, SessionManager
├── protocol/            # Registry, Matcher, Settlement, Identity 客户端
├── distribution/        # 5/25/70 经济分配引擎
├── types.py             # 共享类型定义
├── skills/              # 45+ skills（含项目特定内容）
├── tests/               # 494 tests，100% 通过
├── pyproject.toml       # 独立包配置
├── LICENSE              # AGPL-3.0
├── CODE_OF_CONDUCT.md   # 通用准则
└── CONTRIBUTING.md      # ❌ 仍指向 MAREF
```

### 2.2 文档现状
| 问题 | 严重程度 | 说明 |
|------|---------|------|
| 缺少 README.md | P0 | 新用户无法理解项目 |
| CONTRIBUTING.md 未更新 | P1 | 仍指向 MAREF 仓库 |
| 无独立 docs/ | P1 | 运行规范文档无处可放 |
| 无 .github/workflows/ | P1 | 无 CI/CD |
| skills 含商业引用 | P2 | athena-*, phone-video-factory, jimeng-* 等 |
| 无版本发布流程 | P2 | 无法 pip install |

### 2.3 商业敏感扫描结果
**skills/ 中需处理的引用**：
- `athena-dashboard-design` — 引用 Athena UI v1.1、碳硅共生
- `athena-video-workflow` — 引用 Athena 工作流
- `phone-video-factory` — 含手机号、内部路径、OPC 工具引用
- `jimeng-app-workflow` — 引用即梦 App 内部工作流
- `maref-architecture` — 引用 MAREF 内部架构
- `open-design-api` — 引用 Open Design 内部部署路径
- `samsung-oneui-automation` — 含设备特定信息
- `carbon-silicon-five-principles` — 引用碳硅基共生战略
- `men0-interop` — 引用 Men0 协议内部实现
- `happyhorse-prompt-library` — 含内部项目代号

## 3. 实施计划 (Proposed Changes)

### Phase 1: 文档库建立与代码隔离（立即）

#### 1.1 创建 OPC 工作区 SkillOS 文档库
**目标**：在 OPC 工作区建立 SkillOS 专属文档库，与代码仓库物理隔离

**文件**：`Athena知识库/OPC工作区/项目知识库/skillos/`
```
skillos/
├── 01-项目概述/
│   └── README.md              # 项目介绍、愿景、路线图
├── 02-架构设计/
│   ├── 内核架构.md
│   ├── 协议层设计.md
│   ├── 经济模型.md
│   └── ADR/                   # 架构决策记录
├── 03-开发文档/
│   ├── 本地开发指南.md
│   ├── 测试规范.md
│   └── API 文档/
├── 04-运营与治理/
│   ├── 发布流程.md
│   ├── 安全策略.md
│   └── 社区治理.md
├── 05-审计与合规/
│   └── 审计报告/
└── CROSS_PROJECT.md           # 跨项目索引（引用 OpenHuman 知识库路径）
```

**规则**：
- 商业机密文档（审计、战略、规划）→ 存放在 OPC 工作区
- 运行规范文档（API、部署、开发指南）→ 通过软链接同步到代码仓库 `docs/`
- 代码仓库永不存放商业文档

#### 1.2 建立软链接引用机制
**目标**：代码仓库 `docs/` 通过软链接引用 OPC 工作区文档，保持单一数据源

**操作**：
```bash
# 在 skillos 代码仓库创建 docs/ 目录
mkdir -p /Volumes/1TB-M2/public/skillos/docs

# 创建软链接（运行规范文档）
ln -s "/Volumes/1TB-M2/Athena知识库/OPC工作区/项目知识库/skillos/03-开发文档/本地开发指南.md" \
      /Volumes/1TB-M2/public/skillos/docs/CONTRIBUTING.md
ln -s "/Volumes/1TB-M2/Athena知识库/OPC工作区/项目知识库/skillos/03-开发文档/API 文档/" \
      /Volumes/1TB-M2/public/skillos/docs/api

# CROSS_PROJECT.md 仅存放路径索引，不复制内容
cat > /Volumes/1TB-M2/public/skillos/docs/CROSS_PROJECT.md << 'EOF'
# SkillOS 跨项目知识索引

本文档仅维护路径索引，不复制内容。遵循 CODE_KB_BOUNDARY.md 规范。

## 相关项目

| 项目 | 类型 | 知识库路径 |
|------|------|-----------|
| OpenHuman | 上游生态 | `Athena知识库/执行项目/2026/003-open human/` |
| MAREF | 兄弟项目 | `Athena知识库/OPC工作区/项目知识库/maref/` |
| PERCV | 兄弟项目 | `Athena知识库/OPC工作区/项目知识库/percv/` |

## 文档产地路由

| 文档类型 | 写入位置 |
|---------|---------|
| 运行规范（API、部署） | `docs/`（软链接到 OPC 工作区） |
| 商业机密（审计、战略） | `Athena知识库/OPC工作区/项目知识库/skillos/` |
| 跨项目索引 | `docs/CROSS_PROJECT.md` |
EOF
```

**验证**：
- [ ] 软链接可正常读取
- [ ] 代码仓库无商业文档物理文件
- [ ] OPC 工作区文档可被多个项目引用

#### 1.3 创建 README.md
**目标**：为独立开源项目提供完整的入门文档

**文件**：`/Volumes/1TB-M2/public/skillos/README.md`

**内容结构**：
```markdown
# SkillOS — Skill Execution Kernel

[![CI](https://github.com/skillos-team/skillos/actions/workflows/ci.yml/badge.svg)]()
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License](https://img.shields.io/badge/license-AGPL--3.0-green.svg)](LICENSE)

> 开源 Skill 生态操作系统。管理 Skill 生命周期，执行 5/25/70 经济分配模型。

## 核心能力

### 内核层
- **Entry Kernel** — 20/80 人机路由决策
- **Skill Kernel** — Skill 蒸馏、NFT 铸造、工具链组装、执行
- **Agent Scheduler** — 模型路由 + 拜占庭共识
- **Session Manager** — 会话生命周期管理

### 协议层
- **Registry** — Skill 注册与发现
- **Matcher** — 意图匹配与路由
- **Settlement** — 周期结算（日/周/月）
- **Identity** — 身份认证

### 经济层
- **5/25/70 分配引擎** — 单笔调用收入分配
- **动态权重计算** — 基于贡献度、成功率、治理参与度
- **贡献者池二级分配** — 40/20/10/15/15 角色分配

## 快速开始

```bash
pip install skillos
```

```python
from skillos import SkillKernel, DistributionEngine

kernel = SkillKernel()
manifest = kernel.distill("https://github.com/user/my-skill")
nft = kernel.mint_nft(manifest)
chain = kernel.assemble_tools(nft)
```

## 架构

```
┌─────────────────────────────────────────┐
│           SkillOS Kernel                │
│  EntryKernel → SkillKernel → Scheduler  │
├─────────────────────────────────────────┤
│           Protocol Layer                │
│  Registry | Matcher | Settlement        │
├─────────────────────────────────────────┤
│         Distribution Engine             │
│           5/25/70 Model                 │
└─────────────────────────────────────────┘
```

## 开发

```bash
git clone https://github.com/skillos-team/skillos.git
cd skillos
pip install -e ".[dev]"
pytest tests/ -v --cov
```

## 文档

- [开发指南](docs/CONTRIBUTING.md)
- [API 文档](docs/api/)
- [跨项目索引](docs/CROSS_PROJECT.md)

## License

AGPL-3.0 — 详见 [LICENSE](LICENSE)。
```

#### 1.4 更新 CONTRIBUTING.md
**目标**：替换 MAREF 引用，建立 SkillOS 专属贡献规范

**文件**：`/Volumes/1TB-M2/public/skillos/CONTRIBUTING.md`

**变更点**：
- 仓库地址：`github.com/maref-team/maref.git` → `github.com/skillos-team/skillos.git`
- 项目名称：MAREF → SkillOS
- 安装命令：`pip install -e ".[dev,desktop]"` → `pip install -e ".[dev]"`
- 测试命令：`pytest tests/ -v --cov`（保持不变）
- 添加 SkillOS 特定的代码规范（如 Skill 开发规范）

### Phase 2: Skills 商业脱敏与拆分（短期）

#### 2.1 Skills 分类审计
**目标**：识别并分类所有 skills，确定保留/迁移/脱敏策略

**分类结果**：

| 类别 | Skills | 处理策略 |
|------|--------|---------|
| **通用核心** | writing-skills, test-driven-development, systematic-debugging, subagent-driven-development, verification-before-completion, receiving-code-review, requesting-code-review, executing-plans, finishing-a-development-branch, using-git-worktrees, using-superpowers, dispatching-parallel-agents, cross-platform-content-adaptation, content-calendar, brainstorming, trend-fetch | ✅ 保留在仓库内 |
| **UI/设计通用** | ui-ux-pro-max, svg-animator, animagine-prompt-enhancer | ✅ 保留，脱敏 |
| **平台集成通用** | github-platform, dashscope-platform, deerflow-pipeline, web-automation, vl-phone-automation, samsung-oneui-automation, universal-cli-operator | ⚠️ 保留，移除内部路径 |
| **项目特定** | athena-dashboard-design, athena-video-workflow, phone-video-factory, jimeng-app-workflow, maref-architecture, men0-interop, openhuman-aiag, openhuman-cswdp, openhuman-geo, openhuman-mvp2-saturation, carbon-silicon-five-principles, scarcity-marketing-advisor, social-media-crisis-management, multi-agent-media-orchestration, happyhorse-prompt-library, penta-prompt-generator, llm-script-factory, chinese-drama-script | ❌ 迁移到 skillos-contrib 仓库 |

#### 2.2 创建 skillos-contrib 仓库
**目标**：存放项目特定 skills，与核心仓库解耦

**操作**：
```bash
# 创建独立仓库（GitHub 上）
# github.com/skillos-team/skillos-contrib

# 目录结构
skillos-contrib/
├── athena/                  # Athena 相关 skills
├── openhuman/               # OpenHuman 生态 skills
├── maref/                   # MAREF 集成 skills
├── media-production/        # 视频/媒体生产 skills
├── marketing/               # 营销相关 skills
└── README.md
```

#### 2.3 核心 Skills 脱敏
**目标**：移除通用 skills 中的商业敏感信息

**需脱敏的 skills**：

| Skill | 敏感内容 | 脱敏操作 |
|-------|---------|---------|
| `phone-video-factory` | 手机号 `{{PHONE_REPLACED}}` | 替换为占位符 `<PHONE_NUMBER>` |
| `phone-video-factory` | 内部路径 `/Volumes/1TB-M2/openclaw/...` | 替换为 `<PROJECT_ROOT>/...` |
| `athena-dashboard-design` | "Athena UI v1.1 — 碳硅共生" | 改为 "Dashboard Design System" |
| `open-design-api` | 内部端口 `60479`、脚本路径 | 改为环境变量引用 |
| `samsung-oneui-automation` | 设备特定信息 | 泛化为配置参数 |

**验证**：
```bash
# 扫描敏感信息
grep -rn "{{PHONE_REPLACED}}\|/Volumes/1TB-M2/openclaw\|Athena UI v1.1\|碳硅共生" skills/
# 应返回空结果
```

### Phase 3: CI/CD 独立化（短期）

#### 3.1 创建 .github/workflows/ci.yml
**目标**：建立独立的持续集成流程

**文件**：`/Volumes/1TB-M2/public/skillos/.github/workflows/ci.yml`

**参考 openclaw CI，简化后**：
```yaml
name: SkillOS CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Ruff lint
        run: ruff check .
      - name: Ruff format check
        run: ruff format --check .
      - name: Mypy type check
        run: mypy .

  test:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests with coverage
        run: pytest tests/ -v --cov --cov-report=term

  security:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Bandit SAST
        run: bandit -r . -c pyproject.toml
      - name: pip-audit
        run: pip-audit
```

#### 3.2 创建发布工作流
**文件**：`/Volumes/1TB-M2/public/skillos/.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Build
        run: |
          pip install build twine
          python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

### Phase 4: 版本发布与 PyPI 对接（长期）

#### 4.1 更新 pyproject.toml
**目标**：配置 PyPI 发布元数据

**变更**：
```toml
[project]
name = "skillos"
version = "0.3.0"  # 与当前功能水平对齐
description = "SkillOS - Skill Execution Kernel with 5/25/70 Distribution"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "AGPL-3.0" }
authors = [
    { name = "SkillOS Team", email = "team@skillos.dev" }
]
keywords = ["skill", "agent", "ai", "orchestration", "economic-model"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU Affero General Public License v3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
dependencies = [
    "PyYAML>=6.0",
    "requests>=2.28.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.15.0",
    "mypy>=1.0.0",
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "coverage>=7.0.0",
    "bandit>=1.7.0",
    "pip-audit>=2.0.0",
]

[project.urls]
Homepage = "https://github.com/skillos-team/skillos"
Documentation = "https://skillos.readthedocs.io"
Repository = "https://github.com/skillos-team/skillos"
Issues = "https://github.com/skillos-team/skillos/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### 4.2 创建 CHANGELOG.md
**文件**：`/Volumes/1TB-M2/public/skillos/CHANGELOG.md`

```markdown
# Changelog

## [v0.3.0] — 2026-05-23

### Added
- 独立开源项目拆分，从 OpenHuman 生态解耦
- 独立 CI/CD 配置（GitHub Actions）
- PyPI 发布配置
- 独立文档库（OPC 工作区）
- README.md、CONTRIBUTING.md 独立化

### Changed
- 版本号从 0.1.0 提升至 0.3.0（与功能水平对齐）
- skills/ 目录拆分：通用 skills 保留，项目特定 skills 迁移到 skillos-contrib

### Removed
- OpenHuman/Athena/OpenClaw 商业敏感引用
- 项目特定 skills（athena-*, phone-video-factory, jimeng-* 等）
```

## 4. 假设与决策 (Assumptions & Decisions)

| 决策 | 理由 |
|------|------|
| 文档库存放在 OPC 工作区 | 用户明确要求，便于跨项目统一管理 |
| 软链接引用而非复制 | 保持单一数据源，避免文档漂移 |
| skills 拆分为 core + contrib | 核心仓库保持精简，项目特定内容外迁 |
| 版本号直接跳至 0.3.0 | 代码功能已达原 openclaw v0.3.0 水平 |
| 保留 AGPL-3.0 协议 | 与原协议一致，确保开源传染性 |
| CI 基于 GitHub Actions | 开源社区标准，与 MAREF/PERCV 保持一致 |

## 5. 验证步骤 (Verification)

### Phase 1 验证
- [ ] `README.md` 存在且内容完整
- [ ] `CONTRIBUTING.md` 无 MAREF 引用
- [ ] `docs/` 目录存在，软链接可正常读取
- [ ] `docs/CROSS_PROJECT.md` 仅含路径索引
- [ ] OPC 工作区 `skillos/` 文档库已创建
- [ ] 代码仓库无商业文档物理文件

### Phase 2 验证
- [ ] `grep -r "Athena\|openclaw\|OpenHuman" skills/` 返回空（保留的 skills）
- [ ] `grep -r "{{PHONE_REPLACED}}\|/Volumes/1TB-M2/openclaw" skills/` 返回空
- [ ] skillos-contrib 仓库已创建（GitHub）
- [ ] 迁移的 skills 已从核心仓库移除

### Phase 3 验证
- [ ] `.github/workflows/ci.yml` 存在
- [ ] CI 流程通过（lint + test + security）
- [ ] `.github/workflows/release.yml` 存在

### Phase 4 验证
- [ ] `pyproject.toml` 版本号为 0.3.0
- [ ] `pip install -e .` 安装成功
- [ ] `pytest tests/` 全部通过
- [ ] PyPI 发布流程测试通过（test.pypi.org）

## 6. 时间线

| 阶段 | 预计时间 | 优先级 |
|------|---------|--------|
| Phase 1: 文档库建立 | 1 天 | P0 |
| Phase 2: Skills 脱敏 | 2 天 | P1 |
| Phase 3: CI/CD 独立 | 1 天 | P1 |
| Phase 4: PyPI 发布 | 2 天 | P2 |

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 软链接在 Windows 上不可用 | 中 | 使用相对路径或文档生成脚本替代 |
| Skills 拆分破坏现有工作流 | 高 | 保留过渡期，提供迁移指南 |
| PyPI 名称被占用 | 中 | 提前查询，备选 `skillos-kernel` |
| 社区贡献者找不到文档 | 中 | README 中明确文档位置 |
