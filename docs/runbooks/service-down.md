# Runbook: 服务不可用 (Service Down)

**P0 告警**: `skillos_service_availability < 1`

---

## 1. 检测方法

- Prometheus 告警: `up{job="skillos"} == 0`
- 健康检查端点: `GET /health` 返回非 200
- 用户反馈: 大量"连接超时"投诉

## 2. 影响评估

| 指标 | 评估方法 |
|------|---------|
| 影响用户比例 | `skillos_session_active_count` 下降比例 |
| 收入影响 | `skillos_settlement_amount_usd` 近 5 分钟是否为 0 |
| 错误类型 | 查看 `skillos_errors_total` 按错误类型分布 |

## 3. 恢复步骤

### Step 1: 确认故障范围 (1 min)
```bash
# 检查服务进程
curl -s http://localhost:8080/health

# 检查依赖服务
curl -s http://localhost:9090/-/healthy  # Prometheus
curl -s http://localhost:3000/api/health  # Grafana
```

### Step 2: 检查日志 (2 min)
```bash
# 查看最新 ERROR 日志
tail -n 100 /var/log/skillos/app.log | grep ERROR

# 查看审计日志
tail -n 50 /var/log/skillos/audit.log
```

### Step 3: 判断是否需要回滚 (2 min)
- 如果是最近部署后出现问题 → **执行回滚**
```bash
python scripts/rollback.py --dry-run
python scripts/rollback.py --confirm
```

- 如果是依赖服务故障 → **等待依赖恢复或启用降级模式**

### Step 4: 重启服务 (1 min)
```bash
# 优雅重启
systemctl restart skillos

# 或容器方式
docker-compose restart skillos
```

### Step 5: 验证恢复 (2 min)
```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8080/metrics | grep skillos_requests_total
```

## 4. 沟通模板

```
[INCIDENT] SkillOS 服务不可用
时间: 2026-XX-XX XX:XX UTC
影响: 服务完全不可用，用户无法调用 Skill
状态: 调查中 / 已定位 / 恢复中 / 已恢复
根因: [待填写]
ETA: [预计恢复时间]
```

## 5. 事后复盘 (Post-mortem)

- [ ] 根因分析报告 (24h 内)
- [ ] 预防措施 ticket
- [ ] 监控/告警改进 ticket
