# 06. SkillOS 运维手册

## 监控指标

### RED 指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `skillos_requests_total` | Counter | 按接口/状态码分类的请求总数 |
| `skillos_errors_total` | Counter | 按错误类型分类的错误总数 |
| `skillos_request_duration_seconds` | Histogram | 请求处理时长 |

### 业务指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `skillos_skill_executions_total` | Counter | Skill 执行次数 |
| `skillos_settlement_amount_usd` | Gauge | 结算金额（USD） |
| `skillos_session_active_count` | Gauge | 活跃会话数 |
| `skillos_audit_events_total` | Counter | 审计事件数 |

### 健康检查

```bash
curl http://localhost:8080/health
```

期望返回：
```json
{"status": "ok", "version": "0.3.0"}
```

## 日志查询

### 结构化日志字段

```json
{
  "timestamp": "2026-05-24T08:30:00Z",
  "level": "info",
  "logger": "skillos.kernel",
  "event": "skill_executed",
  "trace_id": "abc123",
  "span_id": "def456",
  "skill_id": "skill-xxx",
  "duration_ms": 120
}
```

### 常用查询

```bash
# 按 trace_id 查询完整链路
jq 'select(.trace_id == "abc123")' /var/log/skillos/*.json

# 查询错误日志
jq 'select(.level == "error")' /var/log/skillos/*.json

# 查询慢请求（>500ms）
jq 'select(.duration_ms > 500)' /var/log/skillos/*.json
```

## 告警响应

### P0 告警（立即响应）

| 告警 | 阈值 | 响应 |
|------|------|------|
| 错误率 > 1% | 5 分钟内 | 查看 Runbook: [service-down](runbooks/service-down.md) |
| P99 延迟 > 2s | 持续 2 分钟 | 查看 Runbook: [traffic-spike](runbooks/traffic-spike.md) |
| 服务不可用 | 任何时间 | 查看 Runbook: [service-down](runbooks/service-down.md) |

### P1 告警（15 分钟内响应）

| 告警 | 阈值 | 响应 |
|------|------|------|
| 错误率 > 0.1% | 10 分钟内 | 检查依赖服务状态 |
| P99 延迟 > 500ms | 持续 5 分钟 | 检查数据库性能 |
| 活跃会话数过高 | > 10000 | 查看 Runbook: [traffic-spike](runbooks/traffic-spike.md) |

## 功能开关管理

### 查看当前开关状态

```python
from skillos.feature_flags import FeatureFlagManager

mgr = FeatureFlagManager()
for flag in mgr.list_flags():
    print(f"{flag.name}: {flag.state.value}")
```

### 调整灰度比例

```python
mgr.update_flag("new_feature", state=FlagState.ROLLOUT, value="50")
```

### 紧急关闭功能

```python
mgr.update_flag("new_feature", state=FlagState.DISABLED)
```

## 数据库运维

### 备份

```bash
# SQLite
cp skillos.db skillos.db.backup.$(date +%Y%m%d)

# PostgreSQL
pg_dump skillos > skillos_backup_$(date +%Y%m%d).sql
```

### 迁移

```bash
# 升级到最新
alembic upgrade head

# 回滚一级
alembic downgrade -1

# 查看当前版本
alembic current
```

## 回滚操作

### 预览回滚

```bash
python3 scripts/rollback.py --dry-run
```

### 执行回滚

```bash
python3 scripts/rollback.py --confirm
```

### 回滚到指定版本

```bash
python3 scripts/rollback.py --to-revision 4c1a8ebff8bb
```

## 部署

详见 [deployment.md](deployment.md)。
