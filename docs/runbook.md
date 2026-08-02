# SkillOS Runbook — 故障处置手册

> **适用范围**: SkillOS v0.5.0-beta
> **配套文档**: `docs/oncall-schedule.md`（轮值表）
> **生效日期**: 2026-07-03

## 1. Runbook 索引

| 编号 | 告警名称 | 严重级别 | 关联组件 | Runbook |
|------|---------|---------|---------|---------|
| RB-001 | Audit Logger 链断裂 | P0 | `skillos/audit.py` | [§2](#rb-001-audit-logger-链断裂) |
| RB-002 | Ed25519 签名验证失败率突增 | P0 | `skillos/security/message_signer.py` | [§3](#rb-002-签名验证失败率突增) |
| RB-003 | Prompt 注入检测命中率异常 | P0 | `skillos/security/prompt_guard.py` | [§4](#rb-003-prompt-注入检测命中率异常) |
| RB-004 | SLO error budget 燃尽 > 50% | P1 | `skillos/kernel/slo.py` | [§5](#rb-004-slo-error-budget-燃尽) |
| RB-005 | DAST ZAP 扫描 FAIL | P1 | `.github/workflows/ci.yml` | [§6](#rb-005-dast-zap-扫描-fail) |
| RB-006 | pre-push hook 阻断推送 | P2 | `scripts/sanitize-for-push.sh` | [§7](#rb-006-pre-push-hook-阻断推送) |
| RB-007 | 数据库连接耗尽 | P1 | `skillos/db/engine.py` | [§8](#rb-007-数据库连接耗尽) |
| RB-008 | 协议客户端熔断器打开 | P1 | `skillos/protocol/*_client.py` | [§9](#rb-008-协议客户端熔断器打开) |

---

## 2. RB-001: Audit Logger 链断裂

**触发条件**: AuditLogger 写入失败 / 链式哈希校验不通过

**症状**:
- 日志中出现 `Audit log failed (event=... actor=... resource=...)`
- `SKILLOS_AUDIT_DIR` 目录磁盘满
- 审计日志文件 HMAC 校验失败

**影响范围**: 审计完整性丧失，合规违规

### 处置步骤

1. **确认告警**
   ```bash
   # 检查审计日志目录
   ls -la $SKILLOS_AUDIT_DIR
   df -h $SKILLOS_AUDIT_DIR  # 磁盘空间

   # 检查最近写入的日志文件
   tail -100 $SKILLOS_AUDIT_DIR/audit_*.jsonl
   ```

2. **磁盘满处置**
   ```bash
   # 归档旧日志
   find $SKILLOS_AUDIT_DIR -name "audit_*.jsonl" -mtime +30 -exec gzip {} \;
   mv $SKILLOS_AUDIT_DIR/audit_*.gz $SKILLOS_AUDIT_DIR/archive/

   # 或扩容磁盘
   ```

3. **HMAC 校验失败处置**
   - 检查 `SKILLOS_AUDIT_SECRET` 是否被意外轮换
   - 若被轮换，恢复为之前的密钥
   - 若密钥泄露，执行密钥轮换流程（见 §2.1）

4. **验证恢复**
   ```bash
   # 触发一条测试审计日志
   python -c "from skillos.audit import log_audit, AuditEventType; log_audit(AuditEventType.AUTH_SUCCESS, 'recovery-test', 'system', 'health-check')"
   # 确认写入成功
   tail -1 $SKILLOS_AUDIT_DIR/audit_*.jsonl
   ```

5. **事后**: 提交事后复盘，分析根因（磁盘容量规划 / 密钥管理流程）

### 2.1 密钥轮换流程

```bash
# 1. 生成新密钥
NEW_SECRET=$(openssl rand -hex 32)

# 2. 停止写入（或进入只读模式）

# 3. 更新环境变量
export SKILLOS_AUDIT_SECRET=$NEW_SECRET

# 4. 重启服务

# 5. 验证新日志链完整性
```

---

## 3. RB-002: 签名验证失败率突增

**触发条件**: `IDENTITY_SIGN` 事件中 `valid: False` 比例 > 5%（5分钟窗口）

**症状**:
- Grafana 签名验证失败率指标突增
- 协议客户端熔断器频繁打开

**影响范围**: 身份确权失败，协议通信中断

### 处置步骤

1. **确认范围**
   ```bash
   # 查询最近的签名验证失败记录
   grep '"valid": false' $SKILLOS_AUDIT_DIR/audit_*.jsonl | tail -50

   # 检查失败的 identity_id 分布
   grep '"valid": false' $SKILLOS_AUDIT_DIR/audit_*.jsonl | jq -r '.actor_id' | sort | uniq -c | sort -rn
   ```

2. **分类排查**
   - **单 identity 失败**: 该 identity 公钥可能被轮换 → 联系对应贡献者确认
   - **多 identity 失败**: 可能是密钥管理服务故障 → 检查 `SKILLOS_API_KEY` 有效性
   - **全部失败**: 可能是 `message_signer` 单例状态异常 → 重启服务

3. **临时缓解**
   ```bash
   # 若确认是密钥同步问题，临时降级为无签名模式（仅限紧急）
   export SKILLOS_DISABLE_SIGNING=1  # 需要代码支持此降级开关
   # 重启服务
   ```

4. **验证恢复**
   - 签名验证失败率降至 < 1%
   - 熔断器恢复关闭状态

5. **事后**: 分析密钥同步延迟根因，补充监控告警阈值

---

## 4. RB-003: Prompt 注入检测命中率异常

**触发条件**: 注入检测命中率突然上升至 > 20%（正常 < 5%）

**可能原因**:
- 真实攻击（Prompt 注入尝试）
- 误报率上升（正则模式过宽）
- 输入分布变化（新业务场景触发误报）

### 处置步骤

1. **确认是真攻击还是误报**
   ```bash
   # 查询最近的注入检测记录
   grep '"is_injection": true' $SKILLOS_AUDIT_DIR/audit_*.jsonl | tail -50

   # 检查匹配的 pattern 类型
   grep '"is_injection": true' $SKILLOS_AUDIT_DIR/audit_*.jsonl | jq -r '.details.matched_patterns[]' | sort | uniq -c | sort -rn
   ```

2. **真攻击处置**
   - 封禁攻击来源 IP / identity_id
   - 提取攻击 payload 样本用于改进检测规则
   - 通知 Escalation Manager

3. **误报处置**
   ```bash
   # 临时降低 guard level（仅限 STANDARD → PERMISSIVE）
   # 修改环境变量
   export SKILLOS_PROMPT_GUARD_LEVEL=permissive
   # 重启服务
   ```
   - 收集误报样本，调整 `prompt_guard.py` 中的正则模式
   - 提交 PR 修复误报

4. **验证恢复**
   - 注入检测命中率回落至正常区间
   - 误报率 < 1%

---

## 5. RB-004: SLO error budget 燃尽

**触发条件**: `SLOManager.compute_error_budget()` 返回剩余 budget < 50%

**症状**:
- Skill 执行延迟 P99 > 500ms
- 错误率 > 1%
- 用户投诉执行超时

### 处置步骤

1. **确认哪个 SLO 燃尽**
   ```bash
   # 查询 SLO 状态
   curl http://localhost:8000/metrics | grep slo_

   # 或直接查询 SLOManager
   python -c "from skillos.kernel.slo import get_slo_manager; m = get_slo_manager(); print(m.compute_error_budget())"
   ```

2. **降级策略**
   ```python
   # 临时降低非核心 SLO 目标
   from skillos.kernel.slo import get_slo_manager
   m = get_slo_manager()
   # 将 availability 目标从 99.9% 降至 99.5%
   m.adjust_target("availability", 0.995)
   ```

3. **限流**
   ```bash
   # 降低请求并发
   export SKILLOS_MAX_CONCURRENT_REQUESTS=10
   # 重启服务
   ```

4. **根因排查**
   - 检查 `kernel_routing` 延迟是否突增 → 可能是模型 API 延迟
   - 检查 `skill_execution` 错误率 → 可能是下游 skill 故障
   - 检查 `protocol_outbound` 错误率 → 可能是协议客户端熔断

5. **验证恢复**
   - error budget 恢复 > 50%
   - P99 延迟 < 500ms

---

## 6. RB-005: DAST ZAP 扫描 FAIL

**触发条件**: GitHub Actions `dast` job 失败

**症状**: PR 被阻断，无法合并

### 处置步骤

1. **查看 ZAP 报告**
   - 在 GitHub Actions 日志中查看 ZAP 输出
   - 下载 ZAP 报告 artifact（HTML 格式）

2. **确认违规规则**
   ```bash
   # 本地复现
   pip install -e ".[dev,web]"
   uvicorn skillos.app:app --port 8000 &
   sleep 3

   # 使用 ZAP CLI 扫描
   zap-cli quick-scan -s xss,sqli -t http://localhost:8000
   ```

3. **修复漏洞**
   - **SQL 注入**: 检查所有 DB 查询使用参数化（`session.query().filter_by()`）
   - **XSS**: 确保 FastAPI 响应使用 JSON（自动转义）
   - **路径遍历**: 检查文件操作使用 `os.path.basename()` 消毒
   - **信息泄露**: 关闭 debug 模式，移除 `/docs` 端点（生产环境）

4. **临时豁免（仅限确认误报）**
   - 在 `.zap/rules.tsv` 中将对应规则改为 `WARN`
   - 在 PR 中说明豁免理由

5. **验证修复**
   - 本地 ZAP 扫描通过
   - CI dast job 通过

---

## 7. RB-006: pre-push hook 阻断推送

**触发条件**: `git push` 时 `athena-sanitize-push` hook 失败

**症状**: 推送被拒绝，终端显示泄露内容

### 处置步骤

1. **查看阻断原因**
   ```bash
   # 查看完整的 hook 输出
   cat .git/hooks/pre-push
   # 手动运行 sanitize 脚本查看详细输出
   bash scripts/sanitize-for-push.sh
   ```

2. **分类处理**

   | 阻断类型 | 处置 |
   |---------|------|
   | 绝对路径泄露 | 将硬编码路径替换为相对路径或环境变量 |
   | 组织名泄露 | 用叙事转化引擎处理（宪法第九条） |
   | 专有文件 | 从仓库中删除该文件 |
   | API Key | 立即轮换密钥 + 从历史中清除 |

3. **⚠️ 严禁绕过**
   - **禁止** `git push --no-verify`（治理红线第 2 条）
   - **禁止** 删除 `.git/hooks/pre-push`
   - 确认修复后重新推送

4. **API Key 泄露处置**
   ```bash
   # 1. 立即轮换密钥
   # 2. 清除 git 历史
   git filter-branch --tree-filter 'rm -f path/to/secret' --prune-empty HEAD
   # 3. 强制推送（需 Escalation Manager 批准）
   git push --force
   ```

---

## 8. RB-007: 数据库连接耗尽

**触发条件**: SQLAlchemy `QueuePool` 超时 / `OperationalError: too many connections`

### 处置步骤

1. **确认连接数**
   ```bash
   # 查看当前连接池状态
   python -c "from skillos.db.engine import get_engine; e = get_engine(); print(e.pool.status())"
   ```

2. **紧急释放**
   ```bash
   # 重启服务释放所有连接
   # 或临时增加连接池大小
   export SKILLOS_DB_POOL_SIZE=20
   export SKILLOS_DB_MAX_OVERFLOW=30
   ```

3. **根因排查**
   - 检查是否有未关闭的 session（`session.close()` 缺失）
   - 检查是否有长事务持有连接
   - 检查 `feature_flags.py` / `session_manager.py` 的 `finally: session.close()` 是否完整

4. **验证恢复**
   - 连接池使用率 < 80%
   - 无 `OperationalError`

---

## 9. RB-008: 协议客户端熔断器打开

**触发条件**: `identity_client` / `settlement_client` / `registry_client` / `matcher_client` 熔断器状态为 open

**症状**: 协议调用直接抛出 `RequestException("Circuit breaker is open")`

### 处置步骤

1. **确认哪个客户端熔断**
   ```bash
   # 查看审计日志中的协议失败记录
   grep -E '"event_type": "(SETTLEMENT_SUBMITTED|IDENTITY_SIGN)"' $SKILLOS_AUDIT_DIR/audit_*.jsonl | grep '"success": false' | tail -20
   ```

2. **检查下游服务状态**
   ```bash
   # 测试下游服务连通性
   curl -sf $SKILLOS_IDENTITY_URL/health
   curl -sf $SKILLOS_SETTLEMENT_URL/health
   ```

3. **等待熔断恢复**
   - 熔断器在 `circuit_timeout=60s` 后自动半开
   - 若下游已恢复，熔断器会自动关闭
   - 若需要立即恢复，重启服务实例

4. **验证恢复**
   - 熔断器状态为 closed
   - 协议调用成功率 > 99%

---

## 附录: 常用诊断命令

```bash
# 检查应用健康状态
curl http://localhost:8000/health

# 查看 Prometheus 指标
curl http://localhost:8000/metrics

# 查看审计日志最近 100 条
tail -100 $SKILLOS_AUDIT_DIR/audit_*.jsonl | jq .

# 查看 SLO 状态
python -c "from skillos.kernel.slo import get_slo_manager; m = get_slo_manager(); print(m.get_status())"

# 检查 pre-push hook 是否安装
ls -la .git/hooks/pre-push

# 运行 sanitize 脚本（手动检查）
bash scripts/sanitize-for-push.sh
```
