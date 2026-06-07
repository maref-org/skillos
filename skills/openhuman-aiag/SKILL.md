---
name: openhuman-aiag
description: "AIAG 身份网关 — OTP 验证、JWT 签发、RBAC 权限管理、Skill-Matcher"
version: "1.0.0"
user-invocable: true
---

# AIAG 身份网关

## 触发条件
- 用户提到身份验证、认证、授权相关操作
- 用户提到 OTP、JWT、RBAC
- 用户需要管理 Skill-Matcher 权限

## 执行步骤

### 1. OTP 验证
- 生成一次性密码（TOTP 算法）
- 验证用户提交的 OTP
- 记录验证日志

### 2. JWT 签发
- 验证身份后签发 JWT Token
- Token 包含：用户 ID、角色、权限、过期时间
- 支持刷新 Token 机制

### 3. RBAC 权限管理
- 角色定义：admin / developer / viewer / agent
- 权限矩阵：
  - admin: 全部操作
  - developer: 读写代码、提交 PR
  - viewer: 只读访问
  - agent: 执行任务、写入产出物

### 4. Skill-Matcher 权限
- 技能注册需要 admin 角色
- 技能调用需要 developer 或 agent 角色
- 技能审查需要 admin 或 reviewer 角色

## 输出格式
```json
{
  "auth_status": "authenticated|denied|expired",
  "token": "jwt-token-string",
  "role": "admin|developer|viewer|agent",
  "permissions": ["read", "write", "execute"],
  "expires_at": "ISO-8601"
}
```

## 安全约束
- JWT 密钥必须从环境变量读取
- OTP 有效期不超过 5 分钟
- 失败尝试超过 5 次锁定 15 分钟
