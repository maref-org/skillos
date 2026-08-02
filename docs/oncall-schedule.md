# SkillOS On-call 轮值表

> **适用范围**: SkillOS v0.5.0-beta 生产环境运维
> **上位法**: Athena 系统宪法 v1.5 + SkillOS 治理框架
> **生效日期**: 2026-07-03

## 1. 角色定义

| 角色 | 职责 | 响应时间 SLA |
|------|------|-------------|
| **Primary On-call** | 第一响应人，接收告警、初步分诊、执行 Runbook | P0: 5min / P1: 15min |
| **Secondary On-call** | Primary 升级后的第二响应人，深度排查 | P0: 10min / P1: 30min |
| **Escalation Manager** | 跨团队协调、决策回滚/熔断 | P0: 15min |

## 2. 轮值排班

### 2.1 周期规则

- **轮值周期**: 1 周（周一 00:00 UTC ~ 周一 00:00 UTC）
- **交接时间**: 每周一 10:00 CST（周一 Standup 时同步交接）
- **交接内容**: 未关闭的 P0/P1 工单、已知异常、进行中的变更

### 2.2 当前排班表

> ⚠️ 以下为模板占位，正式值请替换为团队成员。Beta 阶段轮值以开发团队内部为准。

| 周次 | Primary | Secondary | Escalation Manager |
|------|---------|-----------|-------------------|
| W1 (07/06~07/12) | TBD | TBD | TBD |
| W2 (07/13~07/19) | TBD | TBD | TBD |
| W3 (07/20~07/26) | TBD | TBD | TBD |
| W4 (07/27~08/02) | TBD | TBD | TBD |

### 2.3 替班规则

- 换班需提前 **48 小时** 在团队频道公告
- 紧急无法值班时，直接联系 Escalation Manager 安排替班
- 法定假日由 Escalation Manager 统一编排

## 3. 升级路径

```
告警触发
  │
  ├─ P0 (Critical) → Primary (5min) → Secondary (10min) → Escalation Manager (15min) → 创始人
  │
  ├─ P1 (High) → Primary (15min) → Secondary (30min) → Escalation Manager (60min)
  │
  └─ P2 (Medium) → Primary (2h, 工作时间内)
```

## 4. 联系方式模板

> 以下为模板，正式值请替换。禁止将真实联系方式提交到公共仓库（治理宪法第九条）。

| 角色 | 联系方式 |
|------|---------|
| Primary | Signal: @skillos-primary / Email: oncall-primary@skillos.internal |
| Secondary | Signal: @skillos-secondary / Email: oncall-secondary@skillos.internal |
| Escalation | Signal: @skillos-escalation / Email: escalation@skillos.internal |

## 5. 告警渠道

| 渠道 | 用途 | 配置 |
|------|------|------|
| Prometheus Alertmanager | 自动告警 → Signal 群 | `SKILLOS_METRICS_PORT=9090` |
| Audit Logger 异常 | 审计链断裂 → Email | `SKILLOS_AUDIT_DIR` 监控 |
| SLO 燃尽告警 | error budget 消耗 > 50% → Signal | `SLOManager.compute_error_budget()` |
| DAST Critical | ZAP 扫描 FAIL → GitHub PR 阻断 | `.zap/rules.tsv` FAIL 规则 |

## 6. 工具与访问权限

| 工具 | 用途 | 访问方式 |
|------|------|---------|
| Grafana / Prometheus | 指标看板 | `/metrics` 端点 + `prometheus-client` |
| Audit Log Viewer | 审计日志查询 | `SKILLOS_AUDIT_DIR` 目录 |
| Runbook | 故障处置手册 | `docs/runbook.md` |

## 7. 事后复盘要求

- P0 事件: 24 小时内提交事后复盘文档（`docs/postmortems/YYYY-MM-DD-incident.md`）
- P1 事件: 72 小时内提交事后复盘
- 复盘格式: 时间线 / 影响范围 / 根因 / 改进措施 / 责任人 / 截止日期
