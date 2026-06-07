# 20-03. Runbook: 流量突增 (Traffic Spike)

**P1 告警**: `skillos_requests_total` 5分钟内增长 > 300%

---

## 1. 检测方法

- Prometheus 告警: QPS 突增
- Grafana Dashboard: 请求速率曲线
- 症状: 响应时间增加，部分请求超时

## 2. 影响评估

| 指标 | 阈值 | 行动 |
|------|------|------|
| QPS < 2x 基线 | 正常 | 监控观察 |
| QPS 2-5x 基线 | 警告 | 启用限流 |
| QPS > 5x 基线 | 紧急 | 启用降级 + 扩容 |

## 3. 恢复步骤

### Step 1: 确认流量来源 (2 min)
```bash
# 查看请求来源分布
curl -s localhost:8080/metrics | grep skillos_requests_total | grep user_id

# 查看日志
grep "rate limit" /var/log/skillos/app.log
```

### Step 2: 启用限流 (1 min)
```python
# 通过 feature flag 启用限流
from skillos.feature_flags import get_feature_flag_manager
mgr = get_feature_flag_manager()
mgr.create_flag("rate-limit-enabled", "boolean", "enabled")
```

### Step 3: 启用降级模式 (1 min)
```python
# 关闭非核心功能
mgr.create_flag("disable-skill-discovery", "boolean", "enabled")
mgr.create_flag("disable-settlement-sync", "boolean", "enabled")
```

### Step 4: 扩容 (5 min)
```bash
# Docker Compose 扩容
docker-compose up -d --scale skillos=3

# Kubernetes
kubectl scale deployment skillos --replicas=5
```

### Step 5: 验证
```bash
# 检查响应时间
curl -s localhost:8080/metrics | grep skillos_request_duration_seconds

# 检查错误率
curl -s localhost:8080/metrics | grep skillos_errors_total
```

## 4. 沟通模板

```
[INCIDENT] SkillOS 流量突增
时间: 2026-XX-XX XX:XX UTC
影响: 响应时间增加，部分用户可能遇到超时
状态: 已启用限流和降级，正在扩容
根因: [待确认：推广活动 / 爬虫 / DDoS]
ETA: 10 分钟内恢复正常
```

## 5. 预防措施

- [ ] 配置自动扩容（HPA）
- [ ] 配置 CDN 缓存静态资源
- [ ] 配置 WAF 拦截恶意流量
- [ ] 设置 QPS 基线告警
