# SkillOS 文档库

**版本**: v0.5.0-beta  
**更新日期**: 2026-06-06

---

## 文档索引

| 编号 | 文档 | 说明 |
|------|------|------|
| 01 | [文档索引](01-README.md) | 本文档 — 文档库总览与导航 |
| 02 | [快速开始](02-quickstart.md) | 5 分钟上手 SkillOS |
| 04 | [开发指南](04-development.md) | 本地开发、代码规范、测试 |
| 05 | [API 文档](05-api.md) | 核心模块 API 参考 |
| 06 | [运维手册](06-ops.md) | 监控、日志、告警、健康检查 |
| 07 | [安全白皮书](07-security.md) | 身份认证、传输安全、审计 |
| 08 | [部署文档](08-deployment.md) | 部署流程、灰度发布、回滚 |
| 09 | [测试指南](09-testing.md) | 环境配置、测试分类、CI/CD |
| 12 | [容量规划](12-capacity.md) | 资源估算、扩缩容策略 |
| 13 | [错误预算](13-error_budget.md) | SLO/SLI、错误预算政策 |
| 20 | [应急预案](20-runbooks/) | 5 个运维 Runbook |

---

## 按角色导航

### 开发者
1. [02-快速开始](02-quickstart.md) — 环境搭建
2. [04-开发指南](04-development.md) — 代码规范与测试
3. [05-API 文档](05-api.md) — 接口参考
4. [09-测试指南](09-testing.md) — 测试环境配置

### 运维工程师
1. [06-运维手册](06-ops.md) — 监控与日志
2. [08-部署文档](08-deployment.md) — 部署与回滚
3. [20-应急预案](20-runbooks/) — 故障处理
4. [13-错误预算](13-error_budget.md) — SLO 管理

### 安全工程师
1. [07-安全白皮书](07-security.md) — 安全架构

### 产品经理/架构师
1. [12-容量规划](12-capacity.md) — 资源规划

---

## 根目录保留文件

| 文件 | 说明 |
|------|------|
| [README.md](/README.md) | 项目主页 |
| [CONTRIBUTING.md](/CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](/SECURITY.md) | 安全政策 |
| [CHANGELOG.md](/CHANGELOG.md) | 变更日志 |
| [LICENSE](/LICENSE) | AGPL-3.0 许可证 |
| [CODE_OF_CONDUCT.md](/CODE_OF_CONDUCT.md) | 行为准则 |
| [AGENTS.md](/AGENTS.md) | Agent 操作手册 |

---

## 文档规范

- **编号规则**: `NN-` 前缀，01-19 为核心文档，20-29 为运维文档，30+ 为归档
- **命名规范**: 小写英文，连字符分隔，`.md` 后缀
- **更新要求**: 每次版本发布需同步更新相关文档中的版本号引用
- **归档规则**: 审计报告、工程方案按 `YYYY/MM/` 目录归档
