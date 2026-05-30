# 04. SkillOS 开发指南

**版本**: v0.3.0  
**更新日期**: 2026-05-25

---

## 环境搭建

### 1. 克隆仓库

```bash
git clone https://github.com/skillos-team/skillos.git
cd skillos
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
# 基础开发环境
pip install -e ".[dev]"
```

### 4. 安装 pre-commit hooks

```bash
pre-commit install
```

---

## 代码规范

### 代码风格

- 使用 **Ruff** 进行代码格式化和 lint
- 行长度限制：100 字符
- 使用双引号
- Google 风格文档字符串

### 类型检查

- 所有公共 API 必须添加类型注解
- 使用 **MyPy** 进行静态类型检查
- `disallow_untyped_defs = true`

### 运行检查

```bash
# 代码格式化检查
ruff format --check skillos tests

# 代码风格检查
ruff check skillos tests

# 类型检查
mypy skillos

# 自动修复问题
ruff check --fix skillos tests
ruff format skillos tests
```

---

## 测试

### 测试结构

```
tests/
├── test_skill_kernel.py        # Skill 内核测试
├── test_distribution_engine.py # 分配引擎测试
├── test_entry_kernel.py        # 入口内核测试
├── test_market_layer.py        # 市场层测试
├── test_governance_layer.py    # 治理层测试
├── test_collaboration_layer.py # 协作层测试
├── test_intelligence_layer.py  # 智能层测试
├── test_integration.py         # 集成测试
├── test_e2e.py                 # E2E 测试
├── test_performance.py         # 性能测试
└── test_protocol_resilience.py # 协议韧性测试
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v --cov

# 仅运行单元测试
pytest tests/ -v -k "not test_e2e and not test_performance"

# 运行集成测试
pytest tests/test_integration.py -v

# 运行 E2E 测试
pytest tests/test_e2e.py -v

# 生成覆盖率报告
pytest tests/ --cov=skillos --cov-report=html
```

### 测试标记

| 标记 | 说明 |
|------|------|
| `unit` | 单元测试（快速、无外部依赖） |
| `integration` | 集成测试（需要数据库） |
| `e2e` | 端到端测试（完整链路） |
| `performance` | 性能测试（>5秒） |
| `security` | 安全测试 |

---

## 项目结构

```
.
├── skillos/              # 核心代码
│   ├── kernel/           # L1/L2 内核层
│   ├── market/           # L3 市场层
│   ├── collaboration/    # L4 协作层
│   ├── intelligence/     # L5 智能层
│   ├── governance/       # L6 治理层
│   ├── protocol/         # 协议客户端
│   ├── db/               # 数据库模型与引擎
│   └── observability/    # 可观测性
├── tests/                # 测试代码
├── docs/                 # 文档（编号化）
├── scripts/              # 运维脚本
├── migrations/           # Alembic 数据库迁移
└── observability/        # 监控告警配置
```

---

## Git 工作流

### 分支策略

| 分支 | 用途 | 保护规则 |
|------|------|----------|
| `main` | 生产代码 | 禁止直接推送，需 PR 合并 |
| `develop` | 开发集成 | 禁止直接推送，需 PR 合并 |
| `feature/*` | 功能开发 | 从 develop 创建，合并回 develop |
| `release/*` | 版本发布 | 从 develop 创建，合并到 main 和 develop |
| `hotfix/*` | 紧急修复 | 从 main 创建，合并到 main 和 develop |

### 提交规范

采用 Conventional Commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型:
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档
- `style`: 格式调整
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具
- `security`: 安全修复

示例:
```
feat(market): add dynamic pricing engine

Implement supply-demand based pricing for skill calls.

Closes #123
```

---

## 数据库迁移

### 创建迁移

```bash
alembic revision --autogenerate -m "add market layer tables"
```

### 运行迁移

```bash
alembic upgrade head
```

### 回滚迁移

```bash
alembic downgrade -1
```

---

## 发布流程

1. 更新 `pyproject.toml` 中的版本号
2. 更新 `CHANGELOG.md`
3. 更新 `skillos/version.py`
4. 更新相关文档中的版本引用
5. 创建 Git tag: `git tag -a v0.x.x -m "Release v0.x.x"`
6. 推送 tag: `git push origin v0.x.x`
7. CI 自动构建并发布到 PyPI

---

## 常见问题

### Q: 如何添加新的依赖？

A: 编辑 `pyproject.toml` 中的 `[project.dependencies]` 或 `[project.optional-dependencies]`，然后运行 `pip install -e ".[dev]"`。

### Q: 如何运行特定测试文件？

A: `pytest tests/test_market_layer.py -v`

### Q: 如何调试测试？

A: `pytest tests/test_market_layer.py --pdb`

### Q: 数据库迁移冲突怎么办？

A: 1) 检查 `alembic_version` 表 2) 手动合并迁移文件 3) 测试 `alembic upgrade head`
