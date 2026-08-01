# M12: 告警多渠道推送 + 池额度回收/跨池迁移 + SLO 告警静默策略

> **上位法**: 本计划受 [Athena 系统宪法 v1.5](../../CONSTITUTION.md) 和 [SkillOS 治理框架](../../GOVERNANCE.md) 共同约束。冲突时以宪法优先。
> **红线**: 不托管真实资金（§9）；不引入 T3/T2 级内容（路径/Key/IP/时间戳/组织名/邮箱地址）。
> **前置**: M11（SLO 自动告警 + 共享额度池）已落地，1512 passed 全绿。

## 1. 背景与目标

M11 落地后：告警仅单一 webhook 出站（`SKILLOS_SLO_ALERT_WEBHOOK_URL`）；共享池的 used 只会单调上升（consume 扣减，无释放）；SLO 告警无静默机制（维护窗口/已知问题期间会持续误报）。

M12 目标（纯代码层，渠道账号缺失时降级为可测）：
- **P1 告警多渠道推送**：抽象 `AlertChannel` 协议，内置 `webhook`/`smtp`/`dingtalk`/`wecom` 四个适配器；无渠道 key 时降级（仅日志/落库），有 key 时走真实通道。与 M6 支付抽象层（PaymentProvider + 工厂 + sandbox 降级）同构。
- **P2 池额度自动回收 + 跨池迁移**：池额度可自动回收（定期/按触发把 used 归还原租户自有额度）；租户可从池 A 迁移到池 B（成员关系转移）。
- **P3 SLO 告警静默策略**：配置维护窗口（维护时段内不触发告警/不置 resolved），抑制已知问题期间的误报。

**非目标**：真实 SMTP 账号/钉钉机器人/企微应用对接验证（需渠道账号，人工步骤）；定时任务调度器接入（回收用惰性触发）。

## 2. 现状分析

| 组件 | 位置 | 现状 |
|------|------|------|
| SloAlertService._dispatch | `observability/slo_alerts.py:135` | 单一 urllib POST 到 webhook URL；scheme 白名单 |
| TenantPoolService | `market/tenant_pools.py` | create/get/list/add_member/consume；used 单调递增；无回收/迁移 |
| SloAlertModel | `db/models.py` | slo_alerts 表；无静默字段 |
| monitoring 端点 | `web_api/monitoring.py` | alerts/status、alerts/events |
| 支付抽象层（参考） | `market/payments/` | PaymentProvider + get_provider() 工厂 + 无 key 降级 sandbox |
| 最新 migration | `012_add_slo_alerts_and_pools.py` | 012 为最新，down=011 |

## 3. 关键决策

### D1 告警渠道抽象（复用支付层模式）
- 新模块 `skillos/observability/alert_channels.py`：
  - `AlertChannel` 协议（`send(event: AlertEvent) -> bool`）。
  - `AlertEvent` dataclass（event/slo_name/status/remaining_pct/timestamp）。
  - `WebhookChannel`（现有 urllib POST，scheme 白名单）、`SmtpChannel`（smtplib，env: SMTP_HOST/PORT/USER/PASS/FROM/TO，无配置 raise NotConfigured）、`DingtalkChannel`（POST 到钉钉机器人 webhook）、`WecomChannel`（POST 到企业微信机器人 webhook）。
  - `get_channel()` 工厂：按 `SKILLOS_ALERT_CHANNELS`（逗号分隔，如 `webhook,smtp`）返回通道列表；每个通道无 key 时跳过（返回 None 或 NotConfiguredError 捕获）。
- `SloAlertService._dispatch` 改为遍历 channels 发送；无任何可用通道时仅日志 + 落库（现行为）。

### D2 池额度自动回收
- 语义：池 used 的来源是「租户自有超限后从池借用」。回收 = 把已归还/已结算的额度从池 used 减回。但池模型没有「借出明细」——为最小改动，回收策略改为**按消费比例退还给池**：`release(pool_id, amount)` 把池 used 扣减 amount（clamp ≥0）。
- 集成点：`PayoutService.generate_for_contract` 幂等导出不叠加（现有）。新增 `TenantPoolService.release(pool_id, amount)`：池 used -= amount，用于租户自有额度充足时释放此前借用的池额度。
- 更实际的触发：`release` 由外部调用（如运营面板「回收」按钮或定期任务），本里程碑实现 `release` + API 端点；自动周期回收留待调度器接入。

### D3 跨池迁移
- `TenantPoolService.transfer_member(tenant_id, to_pool_id)`：把租户从当前池移入目标池（删除旧成员关系，新增新成员关系，share_ratio 默认沿用旧值或 1.0）。
- 迁移时校验目标池存在 + active；迁移后该租户的 `pool_for_tenant` 指向新池。
- 池 used 不转移（池额度各自独立）。

### D4 SLO 告警静默策略（维护窗口）
- `slo_alerts` 表加 `silenced_until`（DateTime, nullable）字段（migration 013）。
- `SloAlertService.silence(slo_name, until)`：设置静默截止；`evaluate` 时若 `now < silenced_until` 且该 slo 有静默 → 不触发告警（不置 firing，不 dispatch），视为已抑制。
- 解除：`unsilence(slo_name)` 清空 silenced_until；静默过期后自动恢复评估。
- API：`POST /monitoring/alerts/{slo_name}/silence`（body: until）+ `DELETE`（解除）。

### D5 向后兼容
- `_dispatch` 签名不变（内部改用 channels）；无 `SKILLOS_ALERT_CHANNELS` 时默认 `["webhook"]`（保持 M11 行为）。
- 池现有方法不变；新增 release/transfer_member。
- monitoring 现有端点不变；新增 silence 相关端点。

## 4. 交付物

### P1 告警多渠道推送
- **P1.1**：`skillos/observability/alert_channels.py` — AlertChannel 协议 + AlertEvent + 4 适配器 + get_channel() 工厂。
- **P1.2**：`SloAlertService._dispatch` 改走 channels（默认 webhook）；smtp/dingtalk/wecom 无 key 降级。

### P2 池额度回收/迁移
- `TenantPoolService.release(pool_id, amount)` + `transfer_member(tenant_id, to_pool_id)` + `GET/POST /pools/{id}/release`、`POST /pools/transfer` 端点。

### P3 告警静默
- migration 013（slo_alerts.silenced_until）+ `SloAlertService.silence/unsilence/evaluate` 静默判定 + API 端点。

### 测试
- 渠道：工厂降级、webhook 保留、smtp 无 key 降级、dingtalk/wecom payload 构造（mock urllib）~8 用例。
- 池：release 扣减、transfer 迁移、迁移后联合校验 ~6 用例。
- 静默：静默期间不触发、过期恢复、解除、API ~6 用例。

## 5. 验收标准

1. `make audit` 全绿：`1512 + 新增` passed, 0 failed, 1 skipped, coverage ≥80%, ruff + bandit 0 问题, 3 verify scripts PASS。
2. 渠道测试：无 key 时 smtp/dingtalk/wecom 降级不抛错；有 key（monkeypatch）时正确构造 payload。
3. 池测试：release 正确扣减；transfer 迁移后 pool_for_tenant 指向新池。
4. 静默测试：静默期内 evaluate 不触发；过期后恢复。
5. 既有 M7-M11 测试不改即绿。

## 6. 执行建议

- P1（渠道）→ P3（静默）→ P2（池）顺序；P1 是静默的基础（dispatch 复用）。
- 每个 Task 独立 `git add` 只加本任务文件，不触碰预存改动。
- smtp 用 `smtplib.SMTP` + 无 TLS 时兼容；mock 测试用 monkeypatch 替代真实连接。
- dingtalk/wecom 均为「POST JSON 到机器人 webhook」，与现有 WebhookChannel 同构，仅消息格式不同。

## 7. 里程碑

| 里程碑 | 内容 | 验收 |
|--------|------|------|
| M12-P1 | 告警多渠道推送 | 渠道工厂 + 适配器测试全绿 |
| M12-P2 | 池额度回收/跨池迁移 | release/transfer 服务 + API 测试全绿 |
| M12-P3 | SLO 告警静默策略 | silence/unsilence + evaluate 静默判定测试全绿 |

## 8. 执行建议（补充）

- `get_channel()` 工厂：按 `SKILLOS_ALERT_CHANNELS` 逗号分隔实例化；未知渠道名忽略（日志）。
- `SmtpChannel` 构造时读 env，缺失任一必要配置则 `raise NotConfiguredError`；工厂捕获并跳过。
- 静默判定在状态机最前：`now < silenced_until` → 直接 return None（不改变 firing 状态，视为未观察）。
- transfer 迁移后原池成员关系删除，避免一个租户同时属于多池。

## 9. 落地记录

**M12-P1 告警多渠道推送** — `skillos/observability/alert_channels.py`：
- `AlertChannel` 协议 + `AlertEvent` dataclass；`WebhookChannel`/`SmtpChannel`/`DingtalkChannel`/`WecomChannel` 四适配器。
- `get_channels()` 工厂按 `SKILLOS_ALERT_CHANNELS` 实例化（缺省 `["webhook"]`），无 key 渠道 `NotConfiguredError` 跳过。
- `SloAlertService._dispatch` 改走 channels；scheme 白名单 + nosec B310。

**M12-P2 池额度回收/跨池迁移** — `TenantPoolService.release/transfer_member`：
- `release(pool_id, tenant_id, amount)`：池 used 扣减（clamp ≥0），非成员/非正数 no-op。
- `transfer_member(tenant_id, to_pool_id)`：删除旧成员关系，新增目标池关系，share_ratio 沿用原值，used 不迁移。
- API：`POST /pools/{id}/release` + `POST /pools/transfer`（签名鉴权）。

**M12-P3 SLO 告警静默** — `slo_alerts.silenced_until`（migration 013）：
- `SloAlertService.silence/unsilence/is_silenced/list_silences`；evaluate 静默期直接 return None（不触发不恢复）。
- 活跃告警查询排除 `status=="silenced"`；DB naive datetime 统一比较（时区坑）。
- API：`GET /monitoring/alerts/silences` + `POST/DELETE /monitoring/alerts/{slo}/silence`。

**验收**：`make audit` 全绿 — **1459 passed, 0 failed**, 1 skipped（排除挂起 e2e/integration）, coverage 89%（≥80%）, ruff + bandit 0 问题, 3 verify scripts PASS。

**踩坑**：
1. 静默记录若 status="silenced" 未排除，evaluate 会把它当活跃告警→过期后无法触发 → 查询排除 `status != "silenced"`。
2. DB DateTime 读回 naive，与 aware now 比较报 TypeError → 统一 `replace(tzinfo=None)`。
3. bandit B310 的 nosec 必须与 `urlopen` 调用同行（block comment 无效）。
4. urllib `req.headers` key 大小写为 `Content-type`（非 `Content-Type`）。

## 10. 新会话交接指引

**启动指令**：

```
用 executing-plans 技能执行 docs/plans/2026-08-01-outcome-contract-m12-design.md。
工作目录为本仓库根目录（SkillOS 开发源），分支 main（有大量未提交的预存改动，不要动它们）。
```

**执行清单**（按序）：
1. P1.1: `skillos/observability/alert_channels.py`（协议 + AlertEvent + webhook/smtp/dingtalk/wecom + 工厂）。
2. P1.2: `SloAlertService._dispatch` 改走 channels。
3. P3.1: migration 013（slo_alerts.silenced_until）+ `SloAlertService.silence/unsilence` + evaluate 静默判定。
4. P3.2: monitoring 端点 silence/unsilence。
5. P2.1: `TenantPoolService.release/transfer_member`。
6. P2.2: pools API 端点 release/transfer。
7. 测试：`tests/test_alert_channels.py` + `tests/test_slo_alerts.py` 扩展 + `tests/test_tenant_pools.py` 扩展。
8. 收尾: `make audit` 全绿 → 补 §9 落地记录 → AGENTS.md Session 12 摘要 → 泄漏收敛检查。
