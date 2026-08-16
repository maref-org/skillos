# CSWDP v0.6.0: 碳硅智慧红利协议实现

> **上位法**: 本计划受 [Athena 系统宪法 v2.2](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容（路径/Key/IP/时间戳/组织名/邮箱地址）。
> **前置**: v0.5.0-beta 全绿（1628 passed）；roadmap §5 CSWDP 设计已批准。

## 1. 背景与目标

v0.5.0-beta → v0.6.0 (GA) 之间，roadmap §5 定义 CSWDP（Carbon-Silicon Wisdom Dividend Protocol）为补强组件，路线图批准的代码骨架落地为可运行模块。

CSWDP 目标（纯代码层）：
- **生存保障金**: 按当地最低工资 + 贡献加成计算月度保障金，输出可审计明细（本地最低工资数据由调用方注入，不内嵌国家库）。
- **成本熔断**: 四档预算模式（NORMAL/LOW/CRITICAL/PAUSED），对 LLM 调用等成本敏感操作做前置放行检查。
- **质量门禁**: 自动执行静态扫描 + 测试组合（ruff/mypy/pytest/bandit/pip-audit），输出可审计门禁报告。

**非目标**: 真实资金托管/支付对接（需持牌方）；本地最低工资数据库维护（外部数据源）；WASM/Docker 沙箱（P1 例外 #1，另列）。

## 2. 现状分析

| 组件 | 位置 | 现状 |
|------|------|------|
| CSWDP 模块 | `skillos/cswdp/` | 不存在（本次新建） |
| 质量门禁载体 | 无独立模块 | 零散运行 CI 内脚本；无统一报告模型 |
| `llm` 可选依赖 | `pyproject.toml` | 已声明 `litellm>=1.40.0`（CSWDP 成本熔断可复用报价） |
| 既有幻觉检测 | `skillos/security/hallucination_detector.py` | 5-class 规则版，未接 LLM self-consistency（P1 #4 另列） |

## 3. 关键决策

### D1 模型用纯 dataclass，不引入 ORM
roadmap §5 中 DB 持久化标记为可选。CSWDP 计算无状态（仅输入→输出），采用与 negmarket 一致的 dataclass 模型。持久化留待后续 `db/models.py` 扩展（独立 PR）。

### D2 生存保障金公式（roadmap §5.2.2 固守）
```
base  = 当地最低工资 × 1.5
bonus = base × (历史贡献度×0.4 + 成功率×0.3 + 治理参与×0.3)
total = min(base + bonus, base × 3.0)
```
三个因子均在 `[0,1]` 内 clamp；负收益 clamp 到 0；输出 `describe()` 携带权重/上限/因子明细用于审计。

### D3 成本熔断四档阈值（roadmap §5.2.3 固守）
| 档位 | 剩余预算 | 放行条件 |
|------|----------|----------|
| NORMAL | >30% | 放行 |
| LOW | 10%~30% | 放行 |
| CRITICAL | 2%~10% | 单次成本 ≤ 日预算×2% 放行，否则拒 |
| PAUSED | <2% | 一律拒 |

额外规则：单次预计成本 > 日预算上限 → 一律拒（应走人工审批）。

### D4 质量门禁报告统一模型
`QualityReport` 聚合每项检查的 `QualityCheckResult`（命令/通过/耗时/输出尾部），`evaluate()` 增加覆盖率门槛（默认 ≥80%，可配置）。子进程执行不使用 shell（命令白名单列表参数），规避注入（B603 nosec 注释留痕）。

### D5 API 挂载
`skillos/cswdp/api.py` 按 `negmarket/api.py` 模式独立 router，`app.py` 内 try/except 挂载。

## 4. 文件结构

```
skillos/cswdp/
├── __init__.py       # 聚合导出 + __version__ = 0.6.0
├── models.py         # SurvivalFundRecord / CostCircuitSnapshot / QualityCheckResult / QualityReport
├── survival_fund.py  # SurvivalFundCalculator
├── cost_circuit.py   # CostCircuitBreaker
├── quality_gate.py   # QualityGate
└── api.py            # FastAPI router（4 端点）
tests/test_cswdp.py   # 24 个断言测试
```

## 5. 验收标准

- [x] `ruff check skillos/cswdp/ tests/test_cswdp.py` 全绿
- [x] `bandit -r skillos/cswdp/ -c pyproject.toml` 无 issue（2 处 B603/B404 nosec 留痕）
- [x] 全量 `pytest tests/` 1628 passed（含新增 24 个 CSWDP 测试）
- [x] API 挂载测试通过（TestClient 实测 `/cswdp/survival-fund/calculate` 200）

## 6. 后续（独立 PR）

- P1 例外 #1: WASM/Docker 沙箱替换 process_sandbox
- P1 例外 #4: 幻觉率检测接 LLM self-consistency + 引用验证（复用 `[llm]` litellm 依赖）
- CSWDP DB 持久化（如社区要求）