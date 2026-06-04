# SkillOS 轻量发布门禁

**版本**: v0.3.0 | **覆盖**: SkillOS 专属 10 项发布门禁，替代 43 项通用标准

---

## Gate A: 代码就绪 (Code Readiness)

| # | 检查项 | 通过标准 | 验证方式 | 阻塞 |
|---|--------|---------|---------|:----:|
| A-1 | 单元测试覆盖率 | 总覆盖率 ≥ 70%，核心模块(kernel/distribution) ≥ 85% | `pytest --cov-fail-under=70` | ✅ |
| A-2 | SAST 静态扫描 | 0 Critical, 0 High | `bandit -r kernel/ protocol/ distribution/` | ✅ |
| A-3 | 依赖漏洞审计 | 0 High/Critical CVE | `pip-audit` | ✅ |
| A-4 | 代码规范 | 0 Critical (ruff) | `ruff check kernel/ protocol/ distribution/` | ⚠️ |

## Gate B: 功能验证 (Functional)

| # | 检查项 | 通过标准 | 验证方式 | 阻塞 |
|---|--------|---------|---------|:----:|
| B-1 | 经济模型分配正确性 | 5/25/70 比例精确，二级分配 40/20/10/15/15 可验证 | `python -c "from distribution.engine import *; assert ..."` | ✅ |
| B-2 | 4 种 Intent 路由 | EntryKernel.route() 对 SKILL_CALL/RESEARCH/ANALYSIS/CHAT 返回正确 ExecutionPath | `pytest tests/test_entry_kernel.py -k test_route` | ✅ |
| B-3 | Session 隔离不泄漏 | 创建→执行→清理全链路：资源限制生效 + cleanup 无残留 | `pytest tests/test_session_manager.py -k test_cleanup` | ✅ |

## Gate C: 安全与可观测 (Security & Observability)

| # | 检查项 | 通过标准 | 验证方式 | 阻塞 |
|---|--------|---------|---------|:----:|
| C-1 | 无硬编码密钥 | 0 硬编码密钥/Token/Credential | `trufflehog filesystem .` | ✅ |
| C-2 | 结构化日志 | 核心模块通过 logger 输出结构化日志，包含 trace_id | 日志采样检查 | ⚠️ |
| C-3 | 错误码全覆盖 | API 响应中所有错误码在错误码矩阵中有定义，前端可映射 | 错误码清单审计 | ✅ |

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

---

## 质量评分卡 (SkillOS 定制)

```
评分维度 (满分100):
  功能缺陷率:  30分 (每P0扣15分, P1扣5分)
  安全漏洞率:  25分 (每High扣10分, Critical扣25分)
  测试覆盖率:  20分 (<70% 扣20分, <85%核心扣10分)
  经济模型精度: 15分 (分配误差>0.1%扣15分)
  发布平滑度:  10分 (回滚/故障扣分)

等级:
  A (90-100): 可发布
  B (80-89):  附条件发布
  C (70-79):  需修复 P1 以上问题
  D (<70):    阻塞发布
```

---

## 验证命令速查

```bash
# Gate A
pytest --cov-fail-under=70 --cov=kernel --cov=distribution --cov=protocol
bandit -r kernel/ protocol/ distribution/ -c pyproject.toml
pip-audit
ruff check kernel/ protocol/ distribution/

# Gate B
python -c "
from distribution.engine import DistributionEngine
e = DistributionEngine()
assert abs(e.PLATFORM_RATIO - 0.05) < 1e-9
assert abs(e.ECOSYSTEM_RATIO - 0.25) < 1e-9
assert abs(e.CONTRIBUTOR_RATIO - 0.70) < 1e-9
"
pytest tests/test_entry_kernel.py tests/test_session_manager.py tests/test_distribution_engine.py -v

# Gate C
trufflehog filesystem . --no-verification
# 错误码审计: grep -r "Error\|error_code\|ErrorCode" kernel/ protocol/ distribution/
```
