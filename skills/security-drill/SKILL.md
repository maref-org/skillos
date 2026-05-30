# Skill: security-drill

## 基本信息

| 属性 | 值 |
|------|-----|
| **名称** | security-drill |
| **版本** | 1.0.0 |
| **分类** | security |
| **触发词** | "安全演练", "安全扫描", "渗透测试", "安全审计" |
| **优先级** | P2 |

## 功能描述

执行全栈安全演练：
- Gate 0-5 安全网关全量检查
- 外泄 5 模式检测
- 安全编排 playbook 触发验证
- 审计日志 HMAC 签名验证
- pre-push hook 阻断测试

## 触发场景

- "执行安全演练"
- "运行安全扫描"
- "检查安全合规"
- "安全审计"

## 工具调用链

```
1. athena_check_security_gate — Gate 0-5 全量检查
2. maref_check_exfiltration — 外泄 5 模式检测
3. maref_trigger_playbook — 安全编排验证
4. maref_compliance_check — 合规基线检查
```

## 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| scope | string | 否 | "full"/"gate_only"/"exfiltration_only"（默认: "full"） |
| severity_threshold | string | 否 | "CRITICAL"/"WARNING"/"INFO"（默认: "WARNING"） |

## 输出格式

```json
{
  "drill_id": "DRILL-20260527-001",
  "scope": "full",
  "results": {
    "gates": {"gate_0": "PASS", "gate_1": "PASS", "gate_2": "PASS", "gate_3": "PASS", "gate_4": "PASS", "gate_5": "PASS"},
    "exfiltration": {"alerts": 0, "critical": 0, "warning": 0},
    "playbook": {"triggered": true, "executed": 3},
    "compliance": {"compliant": true, "issues": 0}
  },
  "score": "A",
  "recommendations": []
}
```

## 治理策略

- **FAIL_MODE**: closed（高安全场景阻断）
- **数据级别**: T1（内部安全数据）
- **影响级别**: L4（安全边界）

## 依赖服务

| 服务 | 端口 | 必要性 |
|------|------|--------|
| maref-governance-mcp | 8941 | 必需 |
| athena-orchestrator-mcp | 8150 | 必需 |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | 初始版本 |