# SkillOS 测试环境配置文档

## 1. 环境概述

SkillOS 支持多环境部署：

| 环境 | 用途 | 数据库 | 数据持久化 |
|------|------|--------|-----------|
| 开发 (dev) | 本地开发调试 | SQLite | 本地文件 |
| 测试 (test) | 自动化测试 | SQLite (内存) | 不持久化 |
| 预发 (staging) | 集成验证 | PostgreSQL | 持久化 |
| 生产 (prod) | 线上服务 | PostgreSQL | 持久化 + 备份 |

## 2. 快速开始

### 2.1 开发环境

```bash
# 克隆仓库
git clone <repo-url>
cd skillos

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 初始化数据库
python -c "from skillos.db.engine import init_db; init_db()"

# 运行测试
pytest tests/ -v
```

### 2.2 环境变量

| 变量名 | 开发环境值 | 生产环境值 | 说明 |
|--------|-----------|-----------|------|
| `SKILLOS_DATABASE_URL` | `sqlite:///./skillos.db` | `postgresql://...` | 数据库连接 |
| `SKILLOS_API_KEY` | `dev-key-123` | `<vault-secret>` | API 密钥 |
| `SKILLOS_AUDIT_SECRET` | `dev-audit-secret` | `<vault-secret>` | 审计日志 HMAC 密钥 |
| `SKILLOS_INSECURE` | `1` | 不设置 | 允许 HTTP（仅开发） |
| `SKILLOS_AUDIT_DIR` | `./audit_logs` | `/var/log/skillos/audit` | 审计日志目录 |

### 2.3 测试数据库配置

测试使用内存 SQLite，自动清理：

```python
# conftest.py 中已配置
import os
os.environ["SKILLOS_DATABASE_URL"] = "sqlite:///:memory:"
```

## 3. 测试分类

| 测试类型 | 命令 | 说明 |
|---------|------|------|
| 单元测试 | `pytest tests/ -v` | 核心模块测试 |
| 集成测试 | `pytest tests/test_integration.py -v` | 跨模块集成 |
| E2E 测试 | `pytest tests/test_e2e.py -v` | 端到端流程 |
| 性能测试 | `pytest tests/test_performance.py -v` | 性能基准 |
| 韧性测试 | `pytest tests/test_protocol_resilience.py -v` | 故障注入 |
| 安全扫描 | `bandit -r skillos/ -c pyproject.toml` | SAST |

## 4. CI/CD 集成

GitHub Actions 工作流：

```yaml
# .github/workflows/ci.yml
- lint (ruff, mypy)
- test (pytest with coverage)
- security (bandit, pip-audit, truffleHog)
- dast (ZAP baseline scan)
```

## 5. 常见问题

**Q: 测试失败提示数据库被锁定？**
A: SQLite 并发限制，测试使用内存数据库避免此问题。

**Q: 如何运行单个测试文件？**
A: `pytest tests/test_kernel.py -v -k test_distill`

**Q: 如何生成覆盖率报告？**
A: `pytest tests/ --cov=skillos --cov-report=html`
