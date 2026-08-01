# M9: 租户配额/计费隔离 + 运营面板实时指标

> **上位法**: 本计划受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容（路径/Key/IP/时间戳）。
> **前置**: M8（租户开通 API 化 + 运营面板增强 + 支付沙箱闭环）已落地，1452 passed 全绿。

## 1. 背景与目标

M8 落地后租户可自助开通（draft → active），契约按 tenant_id 归入租户，运营面板（tenant-stats）能聚合契约数/成交额/趋势。但**缺少租户级资源治理**与**实时健康指标**：

1. **无配额/计费隔离**：任意租户可无限生成出款指令（payout），无每租户独立限额 → 存在计费失控风险（一条租户异常可耗尽全平台出款额度）。
2. **运营面板无实时健康指标**：SLO/SLI（`skillos/kernel/slo.py`）已存在但只被监控端点消费，tenant-stats 看板未集成 → 运营无法在面板上一屏看到平台健康状态。

M9 目标：
- **P1 租户配额/计费隔离**：每租户独立出款限额（`payout_limit`），出款指令生成时校验限额，超限拒绝；看板展示配额/用量/剩余。
- **P2 运营面板实时指标**：tenant-stats 增加 `slo` 段（SLOManager 实时 error budget），契约结算等关键路径埋点 availability/latency。

**非目标**：支付宝/微信真实沙箱账号对接（需持牌方测试 key，人工步骤，另行安排）；平台级风控策略；跨租户共享额度池。

## 2. 现状分析

| 组件 | 位置 | 现状 |
|------|------|------|
| TenantModel | `db/models.py:311` | tenant_id/name/status/scene_config，无配额字段 |
| TenantService | `market/tenants.py` | create/set_status/get/list/update_scene_config，无限额/用量方法 |
| PayoutService.generate_for_contract | `market/payouts.py:62` | 幂等生成 contractor 70% + skill_author + platform 5%，无租户限额校验 |
| OutcomeContractModel | `db/models.py:328` | 含 tenant_id（nullable+index），无出款累计字段 |
| tenant-stats | `web_api/outcome.py:303` | stats/trend/contracts 三段，无配额/用量/slo |
| SLOManager | `kernel/slo.py:80` | record_latency/record_availability/compute_error_budget/get_slo_summary，仅被监控端点消费 |
| 最新 migration | `migrations/versions/009_add_tenant_status.py` | 009 为最新，down=008 |

## 3. 关键决策

### D1 配额存于 TenantModel（而非每契约）
- 每租户一行的 `payout_limit`（Float，月出款限额，默认 0 = 不限额）+ `payout_used`（Float，已用出款额，累计）。
- 用「已用额」而非「每次校验后算」，便于看板即时展示剩余。
- 出款指令生成成功后 `payout_used += 指令总额`（记账为准，不做幂等叠加：`generate_for_contract` 已幂等返回现有指令，只在**首次生成**时累加）。

### D2 出款限额校验位置
- 校验在 `PayoutService.generate_for_contract` 首次生成分支：`payout_used + contract.price > payout_limit`（limit>0 时）→ 抛 `PayoutLimitExceededError`。
- 为什么放服务层而非 API 层：`external_agent_demo` / `ip_operations_trial` 等脚本直接调用服务层，需服务层兜底。
- 限额按契约价（price）而非指令总额判断，因指令总额 = price×0.7(contractor) + price×0.7×shares + price×0.05，语义上「租户出款上限」指平台为租户代收代付的契约金额。

### D3 SLO 实时指标集成
- tenant-stats 增加只读 `slo` 段：`get_slo_manager().get_slo_summary()`（含 4 个 SLO 的 target + error_budget.status/remaining_pct）。
- 契约关键路径埋点：`settle()` 成功后 `record_availability("negmarket_api", True)` + `record_latency`（估算，用处理时长）；失败路径 `record_availability(False)`。采用 `negmarket_api` SLO（与出款/契约业务语义对应）。
- 无需新 SLO 配置（复用现有一级），避免配置漂移。

### D4 API 向后兼容
- tenants API：`create`/`get`/`list` 返回新增 `payout_limit`/`payout_used` 字段（缺省 0）；`PUT /tenants/{id}/quota` 新端点设置限额。
- tenant-stats：`stats[]` 每项新增 `payout_limit`/`payout_used`/`payout_remaining`；顶层新增 `slo` 段。旧字段全部保留（M7/M8 测试不动即绿）。

## 4. 交付物

### P1 租户配额/计费隔离
- **P1.1 数据层**：`TenantModel` + `payout_limit`/`payout_used`（Float，server_default 0）；migration `010_add_tenant_payout_quota.py`（幂等，down=009）。
- **P1.2 服务层**：
  - `TenantService.set_payout_quota(tenant_id, limit)`（负数拒绝；0 = 不限额）。
  - `TenantService.get_payout_usage(tenant_id) -> {limit, used, remaining}`。
  - `PayoutService` 新增 `PayoutLimitExceededError`；`generate_for_contract` 首次生成时校验并累加 used。
- **P1.3 API 层**：`PUT /tenants/{id}/quota`（签名鉴权，仅 owner/ops）；tenants create/get/list 返回配额字段；tenant-stats stats[] 展示配额/用量/剩余。

### P2 运营面板实时指标
- `settle()` 埋点 availability/latency（negmarket_api SLO）。
- `tenant-stats` 返回 `slo` 段（get_slo_summary）。

### 测试
- 服务层：配额设置/校验/超限拒绝/幂等不叠加/用量累计 ~8 用例。
- API 层：quota 端点鉴权 + tenant-stats 新字段 ~4 用例。
- SLO：settle 埋点后 tenant-stats.slo 反映健康状态 ~3 用例。

## 5. 验收标准

1. `make audit` 全绿：`1452 + 新增` passed, 0 failed, 1 skipped, coverage ≥80%, ruff + bandit 0 问题, 3 verify scripts PASS。
2. 服务层测试：超限租户出款被拒，正常租户出款成功且 used 累计正确。
3. API 测试：quota 端点幂等 + 鉴权 403/401；tenant-stats 返回 payout_* 与 slo 段。
4. 既有 M7/M8 测试不改即绿（向后兼容）。

## 6. 执行建议

- P1.1 → P1.2 → P1.3 顺序（P1.3 依赖配额字段与校验）；P2 可与 P1 并行（P2 不依赖配额）。
- 每个 Task 独立 `git add` 只加本任务文件，不触碰预存改动。
- 配额累加放在「首次生成」分支内，避免重复导出时叠加。

## 7. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M9-P1 | 租户配额/计费隔离 | 配额服务 + API 测试全绿 |
| M9-P2 | 运营面板实时指标 | settle 埋点 + tenant-stats.slo 测试全绿 |

## 8. 执行建议（补充）

- P1.2 的累加必须在 `generate_for_contract` 的 `if existing: return` 之后，否则幂等导出会重复叠加 used。
- 校验顺序：contract 存在 → status paid → 租户限额 → 生成指令。
- quota 端点鉴权复用 `_require_actor`（Ed25519 签名），仅限注册签名身份。

## 9. 落地记录

（待 M9 执行完成后补记。）

## 10. 新会话交接指引

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m9-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
```

**执行清单**（按序）：
1. P1.1: `db/models.py` TenantModel 加 `payout_limit`/`payout_used`；新建 migration 010（down=009，幂等）。
2. P1.2: `TenantService.set_payout_quota`/`get_payout_usage`；`PayoutService.generate_for_contract` 校验限额 + 累加 used + 抛 `PayoutLimitExceededError`。
3. P1.3: `web_api/tenants.py` 新增 `PUT /tenants/{id}/quota`；create/get/list 返回配额字段；`web_api/outcome.py` tenant-stats stats[] 加 payout_*。
4. P2.1: `outcome_contracts.settle()` 埋点 `get_slo_manager().record_availability`（成功/失败）+ `record_latency`；tenant-stats 顶层返回 `slo` 段。
5. 测试：`tests/test_tenant_quota.py`（服务层）+ `tests/test_tenants_api.py` 扩展 + `tests/test_outcome_api.py` 扩展 + `tests/test_outcome_contracts.py` settle 埋点。
6. 收尾: `make audit` 全绿 → 补 §9 落地记录 → AGENTS.md Session 9 摘要 → 泄漏收敛检查。
