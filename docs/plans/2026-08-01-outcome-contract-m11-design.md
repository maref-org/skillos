# M11: SLO 自动告警推送 + 跨租户共享额度池

> **上位法**: 本计划受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容（路径/Key/IP/时间戳/组织名）。
> **前置**: M10（SLO 趋势曲线 + 平台级跨租户风控）已落地，1479 passed 全绿。

## 1. 背景与目标

M10 落地后 SLO 快照已持久化（slo_snapshots），但**只有被动查询**：运营需主动访问 `/monitoring/slo/trend` 才能看到错误预算；错误预算恶化（burning/exhausted）时无主动通知。同时每租户有独立出款限额，但**无共享额度池**：一个租户额度用尽时，无法从平台/其他租户借用额度，需人工在运营面板调整，缺审批闭环。

M11 目标（纯代码层）：
- **P1 SLO 自动告警推送**：基于 SLO 快照状态机检测「健康→高危」降级，自动出站 webhook 通知（支持 HTTP POST 到配置的告警 URL），并持久化告警记录（含去重/恢复）。
- **P2 跨租户共享额度池**：租户可加入共享额度池，出款限额校验改为「租户自有 + 池共享余额」联合判断；支持池额度调整与审批流（pending → approved/rejected）。

**非目标**：邮件/IM 客户端集成（SMTP/钉钉/企微，需具体渠道账号）；真实沙箱支付账号对接（人工步骤）；复杂审批人配置。

## 2. 现状分析

| 组件 | 位置 | 现状 |
|------|------|------|
| SloSnapshotService | `observability/slo_snapshots.py` | capture 落库 + get_trend；无告警检测 |
| SloSnapshotModel | `db/models.py` | slo_name/status/remaining_pct/sampled_at |
| SLOManager | `kernel/slo.py` | 内存测量 + compute_error_budget（status 计算） |
| monitoring 端点 | `web_api/monitoring.py` | overview/slo/slo-trend；均调用 capture |
| TenantService | `market/tenants.py` | 自有限额（payout_limit/used）；get_platform_payout_risk |
| PayoutService | `market/payouts.py` | generate_for_contract 校验租户限额（PayoutLimitExceededError） |
| 最新 migration | `011_add_slo_snapshots.py` | 011 为最新，down=010 |
| 出站 webhook | `market/payments/` | 入站 webhook 已有（verify_webhook），出站无 |

## 3. 关键决策

### D1 告警状态机（避免重复告警）
- 告警按 `slo_name` 维度维护**当前告警状态**：`none`（正常）→ `firing`（已触发）→ `resolved`（已恢复）。
- 触发条件：status 为 `burning` 或 `exhausted` 时触发；恢复条件：status 回到 `healthy`/`at_risk`。
- **去重**：同一 slo 已在 `firing` 时，即使 snapshot 仍异常也不重复发告警；只在「none→firing」（触发）与「firing→resolved」（恢复）两个沿发送通知。
- 持久化 `slo_alerts` 表记录每次触发/恢复事件（含 payload 快照）。

### D2 告警出站通道（HTTP webhook，无第三方依赖）
- 新服务 `skillos/observability/slo_alerts.py`：`SloAlertService.evaluate(snapshot) -> AlertEvent | None`。
- 出站用标准库 `urllib.request`（无 httpx 依赖，避免引入新依赖）；URL 来自 `SKILLOS_SLO_ALERT_WEBHOOK_URL` 环境变量。
- 无 URL 配置时：告警仍记录到 DB（`firing` 状态 + slo_alerts 事件），只是不实际 HTTP 发送 → 无 key/无配置环境可测。
- HTTP 发送失败不影响主流程（捕获异常，仅日志）。

### D3 共享额度池模型
- 新表 `tenant_pools`：`pool_id`(PK), `name`, `total_limit`(Float), `used`(Float), `status`(active/inactive), `created_at`。
- `tenant_pool_members`：`pool_id`(FK), `tenant_id`(FK), `share_ratio`(Float) — 租户从池可借用额度 = pool.used 之外的剩余按 share_ratio 分配。
- 出款校验升级：`PayoutService.generate_for_contract` 校验「租户自有限额」与「池共享余额」联合：若自有超限，检查所属池剩余；池剩余足够则放行并扣减池 used。
- **审批流**：池额度调整（`PUT /pools/{id}/limit`）创建 `pending` 申请，`POST /pools/{id}/approve|reject` 审批；简单单级审批（无审批人配置，签名身份即审批人）。

### D4 后端兼容
- `PayoutService` 对无池租户行为不变（池校验仅在 `tenant_id` 有归属池时生效）。
- monitoring 现有端点不变；新增 `GET /monitoring/alerts/status`（各 SLO 当前告警状态）。
- tenants 现有配额字段不变；`get_payout_usage` 增加可选的 `pool_available` 字段（向后兼容，缺省不返回）。

## 4. 交付物

### P1 SLO 自动告警推送
- **P1.1 数据层**：`SloAlertModel`（slo_alerts：id/slo_name/status/severity/started_at/resolved_at/payload_json）；`TenantPoolModel`/`TenantPoolMemberModel`（tenant_pools / tenant_pool_members）；migration `012_add_slo_alerts_and_pools.py`（幂等，down=011）。
- **P1.2 服务层**：`skillos/observability/slo_alerts.py` — `SloAlertService`：`evaluate(snapshot)`（状态机 + 去重 + 事件落库 + webhook 出站）、`get_status()`（当前各 SLO 告警状态）、`list_events()`。
- **P1.3 API 层**：`web_api/monitoring.py` — `GET /monitoring/alerts/status`（只读）；`capture()` 后调用 `evaluate()`。

### P2 跨租户共享额度池
- **P2.1 服务层**：`skillos/market/tenant_pools.py` — `TenantPoolService`：`create`/`get`/`list`/`add_member`/`set_limit`（pending 审批）/`approve`/`reject`/`check_available`。
- **P2.2 集成**：`PayoutService.generate_for_contract` 限额校验升级（自有 → 池联合）。
- **P2.3 API 层**：`web_api/pools.py` — `POST /pools`、`GET /pools`、`PUT /pools/{id}/limit`（pending）、`POST /pools/{id}/approve|reject`、`POST /pools/{id}/members`。

### 测试
- 告警：触发/恢复/去重/无 URL 降级/webhook 发送 ~8 用例。
- 池：建池/加成员/限额校验联合/审批流/超池拒绝 ~10 用例。
- API：alerts/status、pools CRUD + 审批鉴权 ~8 用例。

## 5. 验收标准

1. `make audit` 全绿：`1479 + 新增` passed, 0 failed, 1 skipped, coverage ≥80%, ruff + bandit 0 问题, 3 verify scripts PASS。
2. 告警服务：burning/exhausted 触发 → firing；恢复 → resolved；firing 中不重复触发；无 URL 时仍落库。
3. 池服务：限额校验联合（自有 + 池）；超池拒绝；审批流 pending→approved/rejected。
4. 既有 M7-M10 测试不改即绿（向后兼容）。

## 6. 执行建议

- P1.1（数据层两表 + migration）先做，P1/P2 服务层可并行。
- 告警 evaluate 在 capture 后调用，勿影响 capture 主流程（异常吞掉）。
- 池校验：仅当租户有成员关系时启用，否则退回自有限额（旧逻辑）。
- 每个 Task 独立 `git add` 只加本任务文件，不触碰预存改动。

## 7. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M11-P1 | SLO 自动告警推送 | 告警服务 + alerts/status 端点测试全绿 |
| M11-P2 | 跨租户共享额度池 | 池服务 + 联合校验 + 审批流测试全绿 |

## 8. 执行建议（补充）

- webhook 出站用 urllib（`urllib.request.Request`），payload JSON，POST。
- slo_alerts 表 `status` 存当前告警状态（firing/resolved），同一 slo 最多一条「活跃」记录（用唯一约束或查询最新）。
- 池共享余额 = `pool.total_limit - pool.used`；单租户可借 = 池剩余 × share_ratio（share_ratio 归一化到成员之和）。
- 审批：`set_limit` 创建 pending；approve 写 total_limit 并置 active；reject 保持旧值。

## 9. 落地记录

### M11 全阶段落地（2026-08-01，Session 11）

**P1 SLO 自动告警推送**（随 M11 主提交 + 1 安全修复提交）：
- P1.1：`SloAlertModel`（slo_alerts 表：slo_name/status/severity/remaining_pct/started_at/resolved_at/payload）+ `TenantPoolModel`/`TenantPoolMemberModel`/`PoolAdjustmentModel` + migration `012_add_slo_alerts_and_pools.py`（幂等，down=011）。
- P1.2：`skillos/observability/slo_alerts.py` — `SloAlertService.evaluate`（状态机 none→firing→resolved，去重：firing 中不重复触发，仅更新最新值）+ `get_status`（活跃告警，resolved_at IS NULL）+ `list_events`；出站 webhook 用标准库 urllib POST 到 `SKILLOS_SLO_ALERT_WEBHOOK_URL`，无 URL 仅落库。
- P1.3：`web_api/monitoring.py` — `_capture_and_evaluate` 辅助函数（capture 后推进告警状态机，异常吞掉）；`GET /monitoring/alerts/status` + `GET /monitoring/alerts/events`。
- 踩坑：resolve 时若复用原 firing 记录改 status 会丢事件历史 → 保留 firing 记录的触发历史（仅标记 resolved_at），另插一条 resolved 事件；活跃判定须用 `resolved_at IS NULL` 而非 status（否则已恢复记录仍被当活跃）。

**P2 跨租户共享额度池**（同提交）：
- `skillos/market/tenant_pools.py` — `TenantPoolService`：create/get/list/add_member/remove_member/set_limit（pending 审批单）/approve（应用 new_limit）/reject（保持原值）/check_available（池剩余×share_ratio）/consume（扣减池 used）。
- `PayoutService.generate_for_contract` 限额校验升级：自有超限 → 尝试 `pool_svc.consume` 从池借用；池余额不足才抛 `PayoutLimitExceededError`；无池租户行为不变。
- `web_api/pools.py` + api_router 挂载：`POST /pools` / `GET /pools` / `GET /pools/{id}` / `POST /pools/{id}/members` / `PUT /pools/{id}/limit` / `POST /pools/{id}/adjustments/{aid}/approve|reject`（签名鉴权）。

**安全修复**：bandit B310（urllib urlopen 允许 file:/ scheme）中危 → 显式 scheme 白名单（仅 http/https）+ `# nosec B310`。

**最终审计**：`make audit` 全绿 — **1512 passed, 0 failed**, 1 skipped，coverage 89.76%（≥80%），ruff + bandit 0 问题，3 verify scripts PASS。

**真实服务冒烟**：告警 status 端点空库正常；池 API 全链路（注册→建池→加成员→调额申请 pending→审批 approved→总限额 80000 生效 + 成员列表正确）。

**下一步候选（M12）**：告警多渠道推送（SMTP 邮件 / 钉钉 / 企业微信，需渠道账号）；池额度自动回收与跨池迁移；SLO 告警抑制/静默策略（维护窗口）。核心代码层自动化方向持续收敛，人工对接（真实支付/消息渠道）优先。

## 10. 新会话交接指引

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m11-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
```

**执行清单**（按序）：
1. P1.1: `db/models.py` 新增 `SloAlertModel`/`TenantPoolModel`/`TenantPoolMemberModel`；migration 012（down=011，幂等）。
2. P1.2: `skillos/observability/slo_alerts.py` — `SloAlertService.evaluate/get_status/list_events`。
3. P1.3: `web_api/monitoring.py` — capture 后 evaluate + `GET /monitoring/alerts/status`。
4. P2.1: `skillos/market/tenant_pools.py` — `TenantPoolService`（create/get/list/add_member/set_limit/approve/reject/check_available）。
5. P2.2: `PayoutService.generate_for_contract` 联合校验。
6. P2.3: `web_api/pools.py` + 挂载。
7. 测试：`tests/test_slo_alerts.py` + `tests/test_tenant_pools.py` + monitoring/pools API 扩展。
8. 收尾: `make audit` 全绿 → 补 §9 落地记录 → AGENTS.md Session 11 摘要 → 泄漏收敛检查。
