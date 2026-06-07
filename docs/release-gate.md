# SkillOS 轻量发布门禁

**版本**: v0.5.0-beta | **覆盖**: SkillOS 专属 16 项发布门禁，替代 43 项通用标准

---

## Gate A: 代码就绪 (Code Readiness)

| # | 检查项 | 通过标准 | 验证方式 | 阻塞 |
|---|--------|---------|---------|:----:|
| A-1 | 单元测试覆盖率 | 总覆盖率 ≥ 80%，核心模块 ≥ 90% | `pytest --cov-fail-under=80 --cov=kernel --cov=distribution --cov=protocol --cov=negmarket` | ✅ |
| A-2 | SAST 静态扫描 | 0 Critical, 0 High | `bandit -r kernel/ protocol/ distribution/ negmarket/` | ✅ |
| A-3 | 依赖漏洞审计 | 0 High/Critical CVE | `pip-audit` | ✅ |
| A-4 | 代码规范 | 0 Critical (ruff) | `ruff check kernel/ protocol/ distribution/ negmarket/ scripts/` | ✅ |
| A-5 | 结构化日志 | 全模块 JSON 格式输出，trace_id 传播 | `pytest tests/test_logging_config.py -v` | ✅ |
| A-6 | 错误码注册 | 所有错误码在 `kernel/error_codes.py` 注册，矩阵文档存在 | `pytest tests/test_error_codes.py -v` | ✅ |

## Gate B: 功能验证 (Functional)

| # | 检查项 | 通过标准 | 验证方式 | 阻塞 |
|---|--------|---------|---------|:----:|
| B-1 | 经济模型分配正确性 | 5/25/70 比例精确，二级分配 40/20/10/15/15 可验证 | `uv run pytest tests/test_distribution_engine.py -v` | ✅ |
| B-2 | 4 种 Intent 路由 | EntryKernel.route() 对 SKILL_CALL/RESEARCH/ANALYSIS/CHAT 返回正确 ExecutionPath | `pytest tests/test_entry_kernel.py -k TestRoute` | ✅ |
| B-3 | Session 隔离不泄漏 | 创建→执行→清理全链路：资源限制生效 + cleanup 无残留 | `pytest tests/test_session_manager.py -k test_cleanup` | ✅ |
| B-4 | NegMarket 反模式市场 | 上传 → 脱敏 → 生成 AntiPattern Skill → 调用 → 发现 全链路 | `pytest tests/test_negmarket.py tests/test_negmarket_api.py -v` | ✅ |
| B-5 | AgentCard 注册发现 | Agent 注册→发现→心跳→超时摘除全链路 | `pytest tests/test_agent_card.py -v` | ✅ |
| B-6 | 协议网关路由 | A2A/MCP 双协议路由，不支持协议返回明确错误 | `pytest tests/test_protocol_gateway.py -v` | ✅ |

## Gate C: 安全与可观测 (Security & Observability)

| # | 检查项 | 通过标准 | 验证方式 | 阻塞 | 状态 |
|---|--------|---------|---------|:----:|:----:|
| C-1 | 无硬编码密钥 | 0 硬编码密钥/Token/Credential | 手动审计 (trufflehog v2 不支持本地扫描) | ✅ | 通过(手动) |
| C-2 | 结构化日志 | 全模块 JSON 格式，`TraceContext` 传递 trace_id | `pytest tests/test_logging_config.py -v` | ✅ | **v0.5.0-beta 已闭合** |
| C-3 | 错误码全覆盖 | 55 错误码在 `kernel/error_codes.py` 注册，矩阵文档化 | `pytest tests/test_error_codes.py -v` | ✅ | **v0.5.0-beta 已闭合** |

---

## 发布审批矩阵

| 风险等级 | 判定标准 | 审批人 | 门禁要求 |
|---------|---------|--------|---------|
| P0-核心 | 经济模型 / 会话隔离 / 身份认证变更 | 技术负责人 | Gate A+B+C 全绿 |
| P1-重要 | 路由逻辑 / 协议客户端变更 | 团队负责人 | Gate A+B 全绿 |
| P2-一般 | 技能模块 / 工具函数变更 | 代码审查即可 | Gate A-1/A-2 |
| P3-低危 | 文档 / 配置 / 测试用例 | 自动化通过 | 无阻塞 |

---

## AI/Agent 专项验收

SkillOS 核心 AI/Agent 能力的专项验证标准：

| 能力 | 对应模块 | 验收标准 |
|------|---------|---------|
| 20/80 分流 | `EntryKernel.route()` | 每个 `ExecutionPath` 枚举值 (HUMAN_GUI/AGENT_AUTO/HYBRID) 在对应场景下被正确选择 |
| HITL 门禁 | `EntryKernel.human_gate()` | high_risk 关键词触发 PENDING，low_risk 通过，risk_level 判定可复现 |
| 模型级联策略 | `AgentScheduler.cascade()` | 置信度 < 阈值时返回正确升级链路，fallback_chain 非空且无循环 |
| 拜占庭共识 | `AgentScheduler.byzantine_consensus()` | agreement_score < 0.75 触发 arbitration_needed，Jaccard 相似度计算正确 |
| 动态权重 | `DistributionEngine.calculate_weight()` | 4 系数 (0.4/0.3/0.2/0.1) 加权 ≤ 1.0，各输入边界值不崩溃 |
| Session 隔离 | `SessionIsolator` | execute_in_isolation() 超时后 cleanup 无残留进程/文件 |
| 经济模型分配 | `DistributionEngine.distribute()` | 单笔 $1.00: platform=$0.05, ecosystem=$0.25, contributor=$0.70, 二级分配误差 < 1e-6 |
| 身份签名验证 | `IdentityClient.sign()` / `verify_signature()` | Ed25519 签名-验证闭环可重现，篡改后验证失败 |
| 远程桥接 | `RemoteBridge` | 5 种命令类型全部可路由，心跳超时断连可复现 |
| Intent 分类 | `EntryKernel.parse_intent()` | 关键词回退对 6 种 IntentType 正确映射，无假阳性 |
| NegMarket 反模式检测 | `AntiPatternGenerator.call()` | 输入负样本 → 脱敏 → 生成 Skill → 调用返回 risk_level+warning |

---

## 质量评分卡 (SkillOS 定制)

```
评分维度 (满分120):
  功能缺陷率:  30分 (每P0扣15分, P1扣5分)
  安全漏洞率:  25分 (每High扣10分, Critical扣25分)
  测试覆盖率:  20分 (<80% 扣20分)
  经济模型精度: 15分 (分配误差>0.1%扣15分)
  发布平滑度:  10分 (回滚/故障扣分)
  门禁完整性:  10分 (每项 Gate 缺失扣 5 分)
  协议就绪度:  5分  (每项协议缺失扣 2 分)
  KB 对齐度:   5分  (ARCHITECTURE.md 与实际偏差扣分)

等级:
  A (110-120): 可发布
  B (95-109):  附条件发布
  C (80-94):   需修复 P1 以上问题
  D (<80):     阻塞发布
```

---

## 验证命令速查

```bash
# Gate A
uv run pytest --cov-fail-under=80 --cov=kernel --cov=distribution --cov=protocol --cov=negmarket
uv run bandit -r kernel/ protocol/ distribution/ negmarket/ -c pyproject.toml
uv run pip-audit
uv run ruff check kernel/ protocol/ distribution/ negmarket/ scripts/

# Gate B
uv run pytest tests/test_distribution_engine.py -v
uv run pytest tests/test_entry_kernel.py -k TestRoute
uv run pytest tests/test_session_manager.py -k test_cleanup
uv run pytest tests/test_negmarket.py tests/test_negmarket_api.py -v
uv run pytest tests/test_agent_card.py -v
uv run pytest tests/test_protocol_gateway.py -v

# Gate C
# C-1: 手动审计源码确认无硬编码密钥/Token/Credential
uv run pytest tests/test_logging_config.py -v
uv run pytest tests/test_error_codes.py -v

# KB Sync
uv run python scripts/verify_kb_sync.py
uv run python scripts/arch_check.py
uv run python scripts/verify_distribution.py
```
