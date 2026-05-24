# SkillOS — Skill Execution Kernel

[![CI](https://github.com/skillos-team/skillos/actions/workflows/ci.yml/badge.svg)]()
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License](https://img.shields.io/badge/license-AGPL--3.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-705%20passed-brightgreen.svg)]()
[![Audit](https://img.shields.io/badge/audit-B%20grade-blue.svg)]()

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
- **Identity** — Ed25519 身份认证 + 挑战-响应验证

### 经济层
- **5/25/70 分配引擎** — 单笔调用收入分配
- **动态权重计算** — 基于贡献度、成功率、治理参与度
- **贡献者池二级分配** — 40/20/10/15/15 角色分配

### 基础设施层
- **数据持久化** — SQLAlchemy 2.0 + SQLite/PostgreSQL，Alembic 迁移管理
- **可观测性** — Prometheus 指标、OpenTelemetry 分布式追踪、结构化 JSON 日志
- **安全** — HMAC-SHA256 审计日志、HTTPS 强制、API Key 环境变量管理
- **运维** — 功能开关灰度发布、一键回滚、应急预案 Runbooks

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
┌─────────────────────────────────────────────────────────┐
│                    SkillOS Kernel                       │
│       EntryKernel → SkillKernel → Scheduler             │
├─────────────────────────────────────────────────────────┤
│                   Protocol Layer                        │
│        Registry | Matcher | Settlement | Identity       │
├─────────────────────────────────────────────────────────┤
│                  Distribution Engine                    │
│                     5/25/70 Model                       │
├─────────────────────────────────────────────────────────┤
│              Infrastructure Layer                       │
│  DB (SQLAlchemy) | Observability | Security | Ops       │
└─────────────────────────────────────────────────────────┘
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
- [API 文档](docs/api.md)
- [运维手册](docs/ops.md)
- [安全白皮书](docs/security.md)
- [部署文档](docs/deployment.md)
- [跨项目索引](docs/CROSS_PROJECT.md)

## License

AGPL-3.0 — 详见 [LICENSE](LICENSE)。
