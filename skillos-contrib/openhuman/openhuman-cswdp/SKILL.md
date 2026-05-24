---
name: openhuman-cswdp
description: "CSWDP 主权数字化工厂协议 — 五层设计模式、成本熔断、质量门禁"
version: "1.0.0"
user-invocable: true
---

# CSWDP 主权数字化工厂协议

## 触发条件
- 用户提到数字化工厂、CSWDP、主权协议
- 用户需要配置五层设计模式
- 用户需要设置成本熔断或质量门禁

## 执行步骤

### 1. 五层设计模式配置

| 层级 | 名称 | 职责 |
|------|------|------|
| L1 | 入口层 | 20/80 自然语言入口控制器 |
| L2 | 生产层 | 技能蒸馏 + 自动化生产流水线 |
| L3 | 市场层 | 技能 NFT 交易 + 动态定价 |
| L4 | 协作层 | Agent Service Mesh + 智能合约 |
| L5 | 治理层 | SkillDAO + 双 Token 模型 |

### 2. 成本熔断配置
- 日预算上限：$5（默认）
- 四级模式：NORMAL(>30%) / LOW(10-30%) / CRITICAL(2-10%) / PAUSED(<2%)
- 熔断触发：自动降级到下一级
- 恢复条件：预算恢复到阈值以上

### 3. 质量门禁配置
- ruff check 必须通过
- mypy 类型检查必须通过
- pytest 测试覆盖率 >= 80%
- bandit 安全扫描无高危
- pip-audit 无已知漏洞

## 输出格式
```json
{
  "layer_status": {
    "L1": "active|inactive",
    "L2": "active|inactive",
    "L3": "active|inactive",
    "L4": "active|inactive",
    "L5": "active|inactive"
  },
  "budget_mode": "NORMAL|LOW|CRITICAL|PAUSED",
  "budget_remaining_pct": 0.0,
  "quality_gates": {
    "ruff": "pass|fail",
    "mypy": "pass|fail",
    "pytest": "pass|fail",
    "bandit": "pass|fail",
    "pip_audit": "pass|fail"
  }
}
```
