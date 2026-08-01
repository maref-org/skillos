# M10: SLO 趋势曲线 + 平台级跨租户风控面板

> **上位法**: 本计划受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容（路径/Key/IP/时间戳）。
> **前置**: M9（租户配额/计费隔离 + 运营面板实时指标）已落地，1469 passed 全绿。

## 1. 背景与目标

M9 落地后 tenant-stats 已有实时 `slo` 段（错误预算快照）与租户配额字段。但：
1. **SLO 只有快照无趋势**：SLOManager 是内存单例（`_measurements` 不持久化），服务重启即丢历史 → 运营面板无法看到错误预算随时间变化，无法判断「变好/变差」趋势。
2. **无平台级风控总览**：每租户有独立出款限额，但缺少「全平台出款额度总和 / 超限租户告警 / 高风险租户识别」的统一视图 → 平台运营无法一屏掌握全局风险。

M10 目标（纯代码层，无需持牌方 key）：
- **P1 SLO 趋势曲线**：新增 `SloSnapshotModel` 持久化 SLO 快照（status + remaining_pct），提供趋势查询服务与 `GET /monitoring/slo/trend` 端点（近 N 天按日聚合，折线数据）。
- **P2 平台级跨租户风控面板**：`GET /outcome/platform-risk` 汇总全平台出款额度使用（总额/已用/剩余/占用率）、超限租户告警（used ≥ limit）、高风险租户识别（used 逼近 limit ≥80%）。

**非目标**：支付宝/微信真实沙箱账号对接（需持牌方测试 key，人工步骤）；SLO 自动告警推送（邮件/IM，超出当前范围）；跨租户共享额度池。

## 2. 现状分析

| 组件 | 位置 | 现状 |
|------|------|------|
| SLOManager | `kernel/slo.py` | 内存 `_measurements`，无持久化；get_slo_summary 返回实时快照 |
| monitoring 端点 | `web_api/monitoring.py` | overview/slo/metrics 三个只读端点，均无快照落库 |
| app.py 埋点 | `app.py:85-99` | 请求级 record_availability（negmarket_api） |
| TenantService | `market/tenants.py` | get_payout_usage（limit/used/remaining） |
| tenant-stats | `web_api/outcome.py` | stats[] 含每租户配额字段 |
| 最新 migration | `010_add_tenant_payout_quota.py` | 010 为最新，down=009 |

## 3. 关键决策

### D1 SLO 快照持久化模型
- 新表 `slo_snapshots`：`id`(PK), `slo_name`(String,index), `status`(String: healthy/at_risk/burning/exhausted), `remaining_pct`(Float), `sampled_at`(DateTime,index)。
- 只存**快照**（状态+剩余预算百分比）而非原始测量点 → 磁盘/查询成本低，足够支撑趋势图。
- 表结构在 `db/models.py`（与其它模型一致），migration `011_add_slo_snapshots.py`。

### D2 快照捕获时机
- `monitoring/slo` 与 `monitoring/overview` 端点被访问时自动落一条快照（每个 SLO 一条）。
- 提供 `SloSnapshotService.capture(db)`：读 `get_slo_manager().get_slo_summary()` 逐 SLO 落库。
- 快照密度：端点被访问即采样，天然满足「随使用产生历史」。不引入后台定时器（避免进程管理复杂度）。

### D3 趋势查询
- `GET /monitoring/slo/trend?slo_name=negmarket_api&days=7`：按 `sampled_at` 按日聚合，返回每日 `{date, status, remaining_pct}`（取每日最后一条快照）。
- 无数据时返回空列表（不做占位填充，区别于 tenant-stats 的固定天数折线——因为快照是事件驱动非固定密度）。
- `slo_name` 可省略 → 返回所有 SLO 的趋势，结构 `{slo_name: [{date, remaining_pct, status}]}`。

### D4 平台级风控
- 新端点 `GET /outcome/platform-risk`（只读）：
  - `total_limit` / `total_used` / `total_remaining` / `utilization_pct`（全平台出款额度汇总，仅统计 limit>0 的租户）。
  - `over_limit`: [tenant_id...]（used ≥ limit）。
  - `at_risk`: [tenant_id...]（used/limit ≥ 0.8 且 <1.0）。
  - `tenant_count`（活跃租户数）。
- 逻辑放 `TenantService.get_platform_payout_risk()`（复用 get_payout_usage），API 层只做序列化。

### D5 向后兼容
- monitoring 现有端点签名/返回不变；新增 `slo/trend` 子路径。
- tenant-stats 不动（已有 slo 快照段）。platform-risk 是全新端点。

## 4. 交付物

### P1 SLO 趋势曲线
- **P1.1 数据层**：`SloSnapshotModel`（db/models.py）+ migration `011_add_slo_snapshots.py`（幂等，down=010）。
- **P1.2 服务层**：`skillos/observability/slo_snapshots.py` — `SloSnapshotService`：`capture(db)`（读 SLOManager 落库）+ `get_trend(db, slo_name, days)`（按日聚合取末条）。
- **P1.3 API 层**：`web_api/monitoring.py` — `GET /monitoring/slo/trend`（查询趋势，访问时自动 capture）；`monitoring/slo`、`overview` 增加 capture 落库。

### P2 平台级跨租户风控面板
- `TenantService.get_platform_payout_risk()` + `web_api/outcome.py` 新增 `GET /outcome/platform-risk`。

### 测试
- 服务层：capture 落库、get_trend 按日聚合、跨日正确、无数据空列表 ~6 用例。
- API 层：slo/trend 返回结构、platform-risk 汇总/超限/高风险 ~5 用例。

## 5. 验收标准

1. `make audit` 全绿：`1469 + 新增` passed, 0 failed, 1 skipped, coverage ≥80%, ruff + bandit 0 问题, 3 verify scripts PASS。
2. 服务层测试：capture 后 DB 有快照；get_trend 返回正确日聚合；无数据空列表。
3. API 测试：slo/trend 返回 `{slo_name: [{date, remaining_pct, status}]}`；platform-risk 正确计算 utilization/over_limit/at_risk。
4. 既有 M7/M8/M9 测试不改即绿（向后兼容）。

## 6. 执行建议

- P1.1 → P1.2 → P1.3 顺序；P2 可并行（不依赖 SLO）。
- 每个 Task 独立 `git add` 只加本任务文件，不触碰预存改动。
- capture 落库用 `db.add` + `flush`，不 commit（复用请求级 session 生命周期）。

## 7. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M10-P1 | SLO 趋势曲线 | 快照服务 + slo/trend 端点测试全绿 |
| M10-P2 | 平台级跨租户风控 | platform-risk 端点测试全绿 |

## 8. 执行建议（补充）

- `SloSnapshotService.get_trend` 的「每日末条」实现：查询某日全部快照，取 `sampled_at` 最大的一条；用 `datetime` 日期比较而非字符串。
- platform-risk 的 `utilization_pct` 只统计 limit>0 的租户，避免被不限额租户稀释。
- slo/trend 的 `slo_name` 参数 optional；缺省返回全部 SLO 趋势。

## 9. 落地记录

### M10 全阶段落地（2026-08-01，Session 10）

**P1 SLO 趋势曲线**（1 提交）：
- P1.1：`SloSnapshotModel`（slo_snapshots 表：slo_name/status/remaining_pct/sampled_at，后两列带 index）+ migration `011_add_slo_snapshots.py`（幂等，down=010）。
- P1.2：`skillos/observability/slo_snapshots.py` — `SloSnapshotService.capture`（读 SLOManager 逐 SLO 落库，返回条数）+ `get_trend`（按日聚合取当日末条；slo_name 省略时返回 `{slo_name: [points]}`）。
- P1.3：`web_api/monitoring.py` — `overview`/`slo` 访问时自动 capture；新增 `GET /monitoring/slo/trend`（查询前 capture 保证含最新状态）。
- 踩坑：同一天多条快照时间戳相同 → 聚合取末条须用 `>=` 而非 `>`（否则取到首条）；`get_trend` 按日聚合返回每日唯一 key（去重）而非全量点。

**P2 平台级跨租户风控面板**（同提交）：
- `TenantService.get_platform_payout_risk()` — 汇总 limit>0 租户的总额/已用/剩余/占用率；识别 `over_limit`（used≥limit）与 `at_risk`（占用率≥80%）租户；不限额租户不参与统计。
- `web_api/outcome.py` 新增 `GET /outcome/platform-risk`（只读）。

**最终审计**：`make audit` 全绿 — **1479 passed, 0 failed**, 1 skipped，coverage 89.77%（≥80%），ruff + bandit 0 问题，3 verify scripts PASS。

**真实服务冒烟**：`/api/v1/monitoring/slo/trend` 返回 4 个 SLO + 当日快照点；`/api/v1/outcome/platform-risk` 空库正常（tenant_count=0）；路径注意：真实服务端点挂在 `/api/v1` 前缀下（独立测试 FastAPI 无前缀）。

**下一步候选（M11）**：支付宝/微信真实沙箱账号对接执行（需持牌方测试 key，人工步骤）；SLO 自动告警推送（邮件/IM/webhook）；跨租户共享额度池与配额审批流。核心代码层自动落地方向基本收敛，M11 起以人工对接 + 告警运营为主。

## 10. 新会话交接指引

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m10-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
```

**执行清单**（按序）：
1. P1.1: `db/models.py` 新增 `SloSnapshotModel`（slo_snapshots 表）；新建 migration 011（down=010，幂等）。
2. P1.2: `skillos/observability/slo_snapshots.py` — `SloSnapshotService.capture/get_trend`。
3. P1.3: `web_api/monitoring.py` — slo/overview 访问时 capture；新增 `GET /monitoring/slo/trend`。
4. P2: `TenantService.get_platform_payout_risk()` + `web_api/outcome.py` 新增 `GET /outcome/platform-risk`。
5. 测试：`tests/test_slo_snapshots.py`（服务层）+ `tests/test_monitoring_api.py`/`tests/test_outcome_api.py` 扩展（API 层）。
6. 收尾: `make audit` 全绿 → 补 §9 落地记录 → AGENTS.md Session 10 摘要 → 泄漏收敛检查。
