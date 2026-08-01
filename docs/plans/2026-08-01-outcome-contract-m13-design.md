# M13: 池额度自动回收调度器 + SLO 维护窗口周期化

> **上位法**: 本计划受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容（路径/Key/IP/时间戳/组织名/邮箱地址）。
> **前置**: M12（告警多渠道 + 池回收/迁移 + 告警静默）已落地，1459 passed 全绿。

## 1. 背景与目标

M12 落地后：`TenantPoolService.release` 是惰性触发（需外部调用，无自动调度）；`SloAlertService.silence` 是一次性 until（维护窗口需手动设置，无周期化）。

M13 目标（纯代码层）：
- **P1 池额度自动回收调度器接入**：复用现有 `TaskScheduler`（cron 调度，`_invoke_handler` 目前是 stub），新增「周期性释放池额度」handler，把已消费未归还的池额度按策略自动归还。
- **P2 SLO 维护窗口周期化**：从一次性 `until` 升级为 cron 周期维护窗口（如 `0 2 * * 6` 每周六 02:00），evaluate 时命中窗口即抑制告警；一次性 until 兼容保留。

**非目标**：真实 SMTP/钉钉/企微账号对接（人工步骤，需渠道账号）；支付真实沙箱对接（需持牌方 key）。

## 2. 现状分析

| 组件 | 位置 | 现状 |
|------|------|------|
| TaskScheduler | `kernel/task_scheduler.py` | cron 调度已实现；`_invoke_handler` 为 stub（返回固定 dict，handler 未真正接线） |
| TenantPoolService.release | `market/tenant_pools.py` | 惰性释放，外部调用；无自动触发 |
| PayoutService | `market/payouts.py` | 首次生成时自有限额超限→池 consume；幂等导出 |
| SloAlertService.silence | `observability/slo_alerts.py` | 一次性 silenced_until；evaluate 开头判定静默 |
| SloAlertModel | `db/models.py` | 有 silenced_until 列（migration 013） |

## 3. 关键决策

### D1 池额度自动回收策略
自动回收的本质：池 used 的来源是「租户自有超限后从池借用」，契约结算后租户自有用量不再增长，池借用应有机会归还。

但池没有「借出明细」（M11 设计只维护池 used 总额）。为最小改动，回收策略改为**按成员 share_ratio 比例归还**：
- `PoolReclaimService.reclaim()`：遍历活跃池，对每个成员，若该租户自有额度 `usage["used"]` 已低于其 `limit`（即不再超限），则把「超出自有部分」从池 used 释放（由 `release` clamp ≥0 保证不穿负）。
- 触发方式：挂到 `TaskScheduler` 的 cron handler（如 `0 3 * * *` 每日凌晨 3 点），亦可手动调用 API。

> 语义说明：这是「借出方（池）主动回收闲置借用」的运营策略，非严格一对一归还明细——池额度共享，无需精确记账（与 M11 池设计一致）。

### D2 TaskScheduler handler 接线
- `_invoke_handler` 由 stub 升级为**同步/异步统一调用**：handler 形如 `module.function`（如 `skillos.market.pool_reclaim:reclaim`），按 dot 路径动态导入并调用（可同步或 async，统一 await）。
- 新增 `web_api/scheduler.py` 端点：注册任务时校验 handler 可导入，避免运行时才发现错误。
- 保持向后兼容：stub 默认行为替换为「按 handler 路径真实调用」，无 handler 时返回原 stub 结果。

### D3 SLO 维护窗口周期化
- 新表 `maintenance_windows`（`MaintenanceWindowModel`）：`id, slo_name`（`*`=全部）、`cron_expression`（窗口开始时刻）、`duration_minutes`（窗口持续）、`enabled`、`description`。
- `SloAlertService.in_maintenance_window(slo_name, now)`：croniter 判定 now 是否落在某窗口的 [start, start+duration) 内，且 slo_name 匹配。
- `evaluate` 开头：先查维护窗口，命中则直接 return None（与一次性 silence 同一抑制路径）。
- 一次性 `silence/unsilence` 保留不动（维护窗口是另一维度的抑制）。

### D4 迁移
- migration 014 建 `maintenance_windows` 表（幂等，down=013）。
- 无数据迁移（一次性 until 与周期窗口并存，互不覆盖）。

## 4. 交付物

### P1 池额度自动回收
- **P1.1**: `skillos/market/pool_reclaim.py` — `PoolReclaimService.reclaim()`（遍历活跃池按 share_ratio 归还超自有部分）+ `reclaim_scheduled()`（供调度器调用的无参入口，自建 session 后调用）。
- **P1.2**: `TaskScheduler._invoke_handler` 真实接线（dot path 动态导入）。
- **P1.3**: `web_api/scheduler.py` — `POST /scheduler/tasks`（注册，校验 handler）、`GET /scheduler/tasks`、`DELETE /scheduler/tasks/{id}`、`POST /pools/reclaim`（手动触发回收，签名）。

### P2 维护窗口周期化
- **P2.1**: `MaintenanceWindowModel` + migration 014。
- **P2.2**: `SloAlertService` 加 `in_maintenance_window` + `create_maintenance_window/list_maintenance_windows/delete_maintenance_window`；evaluate 命中抑制。
- **P2.3**: monitoring 端点 `POST/GET/DELETE /monitoring/alerts/maintenance`。

### 测试
- 回收：超自有部分归还、未超自有不动、clamp、调度器接线 ~8 用例。
- 窗口：命中抑制、未命中不抑制、`*` 全量、一次性 until 兼容 ~6 用例。

## 5. 验收标准

1. `make audit` 全绿：`1459 + 新增` passed, 0 failed, 1 skipped, coverage ≥80%, ruff + bandit 0 问题, 3 verify scripts PASS。
2. 回收测试：池 used 正确减少，非超限租户不受影响，手动 API 返回回收量。
3. 窗口测试：cron 命中窗口时 evaluate 返回 None，窗口外正常告警。
4. 既有 M11-M12 测试不改即绿。

## 6. 执行顺序

- P1.1 回收服务 → P1.2 调度器接线 → P1.3 端点 → P2.1 数据层 → P2.2 服务 → P2.3 端点 → 测试 → 收尾。

## 7. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M13-P1 | 池额度自动回收 + 调度器接线 | 回收服务 + 调度器测试全绿 |
| M13-P2 | 维护窗口周期化 | 窗口服务 + API 测试全绿 |

## 8. 踩坑预案

- TaskScheduler 的 `_invoke_handler` 被 `web_api/system.py` 的 `scheduled_tasks()` 使用，改 stub 时保持返回 dict 结构，避免破坏既有端点。
- croniter 判定「now 在窗口内」：窗口开始 = croniter.get_next(now)，再比较 duration；需容忍 now 恰在窗口开始边缘。
- 回收服务的 reclaim() 需接受外部 db_session（供 API/测试复用）与内部自建 session（供调度器）两种入口。

## 9. 落地记录

**M13-P1 池额度自动回收 + 调度器接线** — `skillos/market/pool_reclaim.py`：
- `PoolReclaimService.reclaim()`：遍历活跃池，按成员「自有富余量」归还超自有部分的池 used（share_ratio 封顶，clamp ≥0）；`reclaim_scheduled()` 供调度器无参入口（自建 session）。
- `TaskScheduler._invoke_handler` 由 stub 升级为 dot path 动态导入（`module:func` 或 `module.func`），同步/异步统一 await，失败返回 error dict。
- `web_api/scheduler.py`：`POST/GET/DELETE /scheduler/tasks` + enable/disable + `POST /pools/reclaim`（均签名鉴权）；注册时校验 handler 可导入。

**M13-P2 SLO 维护窗口周期化** — `maintenance_windows` 表（migration 014）：
- `MaintenanceWindowModel`（slo_name 支持 `*` 全量）+ `SloAlertService.in_maintenance_window`（croniter get_prev 判定 [触发, +duration) 内）+ 窗口 CRUD。
- `evaluate` 命中维护窗口直接 return None（与一次性 silence 并存、互不覆盖）。
- monitoring 端点 `POST/GET /monitoring/alerts/maintenance` + `DELETE /{id}`。

**验收**：`make audit` 全绿 — **1483 passed, 0 failed**, 1 skipped（排除挂起 e2e/integration）, coverage 89%（≥80%）, ruff + bandit 0 问题, 3 verify scripts PASS。

**踩坑**：
1. `get_session` 是普通 generator（无 @contextmanager 装饰），`with get_session() as db` 会失败 → 调度器入口用 `get_sessionmaker()()` 手动建 session。
2. TaskScheduler 的 `_invoke_handler` 被 `web_api/system.py` 的 `scheduled_tasks()` 复用，接线时保持返回 dict 结构不破坏既有端点。
3. 单 Body 参数需 `embed=True`（维护窗口/回收端点）。
4. 签名鉴权测试须用 `sign_headers(payload)` 且 payload 与实际请求 body 一致，否则 401。

## 10. 新会话交接指引

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m13-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
```

**执行清单**（按序）：
1. P1.1: `skillos/market/pool_reclaim.py`（PoolReclaimService.reclaim + reclaim_scheduled）。
2. P1.2: `TaskScheduler._invoke_handler` 真实接线（dot path 动态导入）。
3. P1.3: `web_api/scheduler.py`（scheduler 任务 CRUD）+ `POST /pools/reclaim`。
4. P2.1: migration 014（maintenance_windows 表）+ `MaintenanceWindowModel`。
5. P2.2: `SloAlertService.in_maintenance_window` + 窗口 CRUD + evaluate 命中抑制。
6. P2.3: monitoring 端点 maintenance 窗口 CRUD。
7. 测试：`tests/test_pool_reclaim.py` + `tests/test_maintenance_window.py` + `tests/test_scheduler_api.py`。
8. 收尾: `make audit` 全绿 → 补 §9 落地记录 → AGENTS.md Session 13 摘要 → 泄漏收敛检查。
