# SkillOS 安全白皮书

## 安全模型

SkillOS 采用纵深防御策略，从身份认证、传输安全、审计追踪、输入校验四个层面构建安全体系。

## 身份认证

### Ed25519 数字签名

- 算法：Ed25519（RFC 8032）
- 密钥长度：私钥 32 字节，公钥 32 字节，签名 64 字节
- 特性：确定性签名、快速验证、抵抗侧信道攻击

### 挑战-响应协议

```
Client                          Server
  |                               |
  | -------- request_challenge -->|
  |<-- challenge (random nonce) --|
  |                               |
  | ---- sign(challenge) -------->|
  |<-- verify & issue token ------|
```

### API Key 管理

- 存储：环境变量 `SKILLOS_API_KEY`
- 禁止：代码中硬编码、日志中输出、URL 参数传递
- 轮换：预留轮换接口，建议 90 天周期

## 传输安全

### HTTPS 强制

- 生产环境：仅允许 HTTPS
- 开发环境：`--insecure` flag 允许 HTTP（仅限 localhost）
- 协议客户端：默认 `https://`，自动拦截 `http://`

### 证书验证

- 生产环境：验证服务器证书
- 开发环境：可选跳过证书验证（`verify=False`）

## 审计日志

### HMAC-SHA256 链式签名

```
Record N:  data + HMAC(prev_signature + data)
```

- 密钥：独立审计密钥，与业务密钥分离
- 存储：append-only 文件，权限 0600
- 验证：可逐条验证签名链完整性

### 覆盖范围

| 操作类型 | 记录内容 |
|----------|----------|
| 身份认证 | user_id, challenge, result, timestamp |
| Skill 执行 | skill_id, inputs_hash, outputs_hash, duration |
| 结算 | amount, currency, contributors, tx_hash |
| 状态变更 | entity_type, entity_id, old_state, new_state |

## 输入校验

### 参数校验

- 类型校验：Python 类型注解 + 运行时检查
- 范围校验：数值范围、字符串长度、枚举值
- 格式校验：URL、UUID、日期时间

### 安全边界

| 边界 | 措施 |
|------|------|
| 用户输入 | 白名单校验、长度限制、转义处理 |
| 文件上传 | 类型白名单、大小限制、病毒扫描（预留） |
| 数据库查询 | 参数化查询、ORM 转义、禁止拼接 SQL |
| 外部请求 | 超时限制、响应大小限制、Schema 校验 |

## 漏洞管理

### 依赖扫描

```bash
# Python 依赖漏洞扫描
pip-audit

# 密钥泄露扫描
truffleHog filesystem .

# 代码安全扫描
bandit -r skillos/
```

### 已知漏洞

| CVE | 组件 | 状态 |
|-----|------|------|
| CVE-2026-3219 | pip 26.0 | 待升级（不影响运行时） |
| CVE-2026-6357 | pip 26.0 | 待升级（不影响运行时） |

## 应急响应

### 数据泄露

详见 [runbooks/data-breach.md](runbooks/data-breach.md)。

### 服务不可用

详见 [runbooks/service-down.md](runbooks/service-down.md)。

## 合规

- 日志保留：审计日志保留 1 年
- 数据加密：传输 TLS 1.3，存储预留字段级加密
- 访问控制：RBAC 预留接口
