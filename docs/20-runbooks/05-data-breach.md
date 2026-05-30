# 20-05. Runbook: 数据泄露 (Data Breach)

**P0 告警**: 安全团队报告 / 用户投诉 / 异常访问模式

---

## 1. 检测方法

- 审计日志异常: 大量 `AUTH_FAILURE` 后突然 `AUTH_SUCCESS`
- 数据库访问日志: 非业务时间的大量查询
- 外部报告: HackerOne / 用户邮件 / 监管通知

## 2. 影响评估

| 数据类型 | 严重程度 | 行动 |
|---------|---------|------|
| 用户身份信息 | Critical | 立即通知用户 + 监管 |
| 审计日志 | High | 验证日志完整性 |
| Skill 元数据 | Medium | 评估商业影响 |
| 结算记录 | High | 验证财务数据完整性 |

## 3. 恢复步骤

### Step 1: 隔离受影响系统 (5 min)
```bash
# 暂停外部访问
iptables -A INPUT -p tcp --dport 8080 -j DROP

# 或切换维护模式
python -c "
from skillos.feature_flags import get_feature_flag_manager
mgr = get_feature_flag_manager()
mgr.create_flag('maintenance-mode', 'boolean', 'enabled')
"
```

### Step 2: 保留证据 (10 min)
```bash
# 备份当前日志
cp -r /var/log/skillos /var/log/skillos-incident-$(date +%s)

# 备份数据库
cp skillos.db skillos-incident-$(date +%s).db

# 导出审计链
python -c "
from skillos.audit import AuditLogger
logger = AuditLogger()
with open('audit-export-incident.json', 'w') as f:
    f.write(logger.export())
"
```

### Step 3: 验证审计链完整性
```python
from skillos.audit import AuditLogger
logger = AuditLogger()
if logger.verify_chain():
    print("Audit chain intact")
else:
    print("ALERT: Audit chain compromised!")
```

### Step 4: 轮换密钥 (15 min)
```bash
# 轮换 API Key
export SKILLOS_API_KEY=$(openssl rand -hex 32)

# 轮换审计日志密钥
# 需要重启服务以加载新密钥
systemctl restart skillos
```

### Step 5: 通知相关方
```
[SECURITY INCIDENT] SkillOS 数据泄露
时间: 2026-XX-XX XX:XX UTC
影响: [待评估] 用户数据可能泄露
状态: 系统已隔离，正在调查
行动: 密钥已轮换，审计日志已备份
联系人: security@skillos.dev
```

## 4. 事后复盘

- [ ] 根因分析（24h 内）
- [ ] 影响范围评估
- [ ] 监管通知（如适用）
- [ ] 用户通知（如适用）
- [ ] 安全加固措施
- [ ] 渗透测试

## 5. 预防措施

- [ ] 定期轮换 API Key
- [ ] 启用 MFA
- [ ] 数据库访问审计
- [ ] 最小权限原则
- [ ] 定期安全扫描
