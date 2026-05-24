# Changelog

## [v0.3.0] — 2026-05-24

### Security
- Ed25519 真实签名替换 SHA256 模拟签名
- 身份验证实现挑战-响应完整流程
- 强制 HTTPS，禁止明文 HTTP（开发环境 `--insecure` flag）
- API Key 从环境变量 `SKILLOS_API_KEY` 读取，禁止硬编码
- HMAC-SHA256 审计日志，append-only + 链式验证
- 统一错误码体系，所有公共方法参数校验

### Data Persistence
- SQLAlchemy 2.0 ORM 引入，支持 SQLite/PostgreSQL
- 数据模型：Skill、Session、DistributionRecord、Identity、AuditLog、FeatureFlag
- Repository 模式封装 CRUD
- Alembic 数据库迁移管理
- 进程重启后数据可恢复

### Observability
- Prometheus RED 指标（Rate/Errors/Duration）
- OpenTelemetry 分布式追踪，自动 trace_id 传播
- structlog 结构化 JSON 日志，自动注入 trace_id/span_id
- 告警规则：P0/P1/P2 三级告警配置

### Quality
- 协议客户端韧性测试 75 个（熔断、重试、HTTPS、边界值）
- 集成测试 44 个（全链路生命周期验证）
- E2E 测试 11 个（完整用户场景）
- 性能测试 15 个（明确 SLA 阈值）
- 全量测试 705 通过，零回归

### Operations
- 功能开关（Feature Flags）：boolean/percentage/user_list/canary
- 版本管理与一键回滚脚本
- 5 个应急预案 Runbook（服务不可用、DB 故障、依赖故障、流量突增、数据泄露）
- 自动化部署脚本（测试 → 安全扫描 → 迁移 → 健康检查）

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
