# Runbook: 依赖服务故障 (Dependency Failure)

**P1 告警**: `skillos_circuit_breaker_open > 0`

---

## 1. 检测方法

- Prometheus 告警: 熔断器打开
- 日志: `Circuit breaker is open`
- 症状: 外部 API 调用持续失败

## 2. 影响评估

| 依赖服务 | 影响 |
|---------|------|
| Registry Client | 无法注册/发现 Skill |
| Matcher Client | 无法匹配 Skill，返回本地 fallback |
| Settlement Client | 无法提交结算记录，本地缓存 |
| Identity Client | 无法验证身份，本地验证仍可用 |

## 3. 恢复步骤

### Step 1: 确认依赖状态 (1 min)
```bash
# 检查各服务端点
curl -s https://registry.skillos.dev/health
curl -s https://matcher.skillos.dev/health
curl -s https://settlement.skillos.dev/health
```

### Step 2: 检查熔断器状态
```bash
# 查看应用日志
grep "circuit" /var/log/skillos/app.log

# 查看指标
curl -s localhost:8080/metrics | grep skillos_circuit_breaker
```

### Step 3: 等待自动恢复
熔断器会在 `_circuit_timeout`（默认 60s）后自动半开：
- 如果依赖恢复，请求成功 → 熔断器关闭
- 如果依赖仍失败 → 熔断器重新打开

### Step 4: 手动重置熔断器 (如需)
```python
from skillos.protocol.registry_client import RegistryClient
client = RegistryClient()
client._circuit_failures = 0
client._circuit_last_failure = 0
```

### Step 5: 验证恢复
```bash
# 测试各客户端
curl -s localhost:8080/metrics | grep skillos_requests_total
```

## 4. 降级策略

当依赖不可用时，系统会自动降级：

| 客户端 | 降级行为 |
|-------|---------|
| RegistryClient | 返回缓存数据 |
| MatcherClient | 返回空候选列表 |
| SettlementClient | 本地缓存，稍后重试 |
| IdentityClient | 本地验证（已缓存的公钥） |

## 5. 预防措施

- [ ] 配置依赖服务健康检查
- [ ] 设置熔断器阈值告警
- [ ] 监控依赖服务 P99 延迟
- [ ] 配置依赖服务备用地址
