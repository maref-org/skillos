# 20-02. Runbook: 数据库故障 (Database Failure)

**P0 告警**: `skillos_db_connection_errors > 0`

---

## 1. 检测方法

- Prometheus 告警: 数据库连接池耗尽
- 应用日志: `sqlalchemy.exc.OperationalError`
- 症状: 所有写操作失败，读操作可能正常（缓存命中）

## 2. 影响评估

| 场景 | 影响 |
|------|------|
| SQLite 文件损坏 | 所有持久化操作失败，内存缓存仍可用 |
| PostgreSQL 连接池耗尽 | 新请求排队，超时后失败 |
| 磁盘空间不足 | 写操作失败，读操作正常 |

## 3. 恢复步骤

### Step 1: 确认数据库状态 (1 min)
```bash
# SQLite
sqlite3 skillos.db ".tables"
sqlite3 skillos.db "PRAGMA integrity_check;"

# PostgreSQL
psql -h localhost -U skillos -c "SELECT 1;"
psql -h localhost -U skillos -c "SELECT count(*) FROM pg_stat_activity;"
```

### Step 2: 检查磁盘空间 (1 min)
```bash
df -h
du -sh skillos.db
```

### Step 3: 启用只读降级模式 (2 min)
如果数据库暂时无法恢复，启用只读模式：
```python
# 在 feature flag 中启用
from skillos.feature_flags import get_feature_flag_manager
mgr = get_feature_flag_manager()
mgr.create_flag("read-only-mode", "boolean", "enabled")
```

### Step 4: 数据库修复

**SQLite 损坏**:
```bash
# 备份当前数据库
cp skillos.db skillos.db.bak.$(date +%s)

# 尝试修复
sqlite3 skillos.db ".dump" | sqlite3 skillos_fixed.db
mv skillos_fixed.db skillos.db
```

**PostgreSQL 连接池耗尽**:
```sql
-- 查看活跃连接
SELECT pid, state, query_start, query 
FROM pg_stat_activity 
WHERE datname = 'skillos';

-- 终止空闲连接
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' AND datname = 'skillos';
```

### Step 5: 从备份恢复 (如需)
```bash
# 使用最新备份
pg_restore -h localhost -U skillos -d skillos skillos_backup_latest.dump

# 或 SQLite
cp skillos_backup_latest.db skillos.db
```

## 4. 预防措施

- [ ] 配置数据库连接池上限告警
- [ ] 设置自动备份（每日）
- [ ] 监控磁盘空间使用率
- [ ] 配置只读降级开关
