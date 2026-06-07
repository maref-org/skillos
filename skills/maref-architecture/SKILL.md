---
name: maref-architecture
description: |
version: "1.0.0"
  MAREF（Multi-Agent Resilience & Evolution Framework）多Agent韧性进化框架。
  独立开源的易经哲学多Agent架构，可独立运行完整Agent集群或与Skillos组合使用。
  触发条件：多Agent编排、韧性设计、故障注入、进化安全、河图策略、Agent集群管理。
---

# MAREF 架构

## 设计哲学

根植于《易经》阴阳动态平衡与华夏5000年文明验证的系统论智慧：
- **阴阳平衡** → Agent自治 vs 人类管控的动态张力
- **五行相生相克** → 五项目生态循环（木=Athena / 火=OpenClaw / 土=OpenHuman / 金=MAREF / 水=Skillos）
- **变易·简易·不易** → Agent演化三原则

## 16状态机

从 CREATED 到 ARCHIVED 共16个状态，TLA+ 形式化验证确保无死锁。

## 三大消息族规范

| 消息族 | 核心功能 |
|--------|---------|
| **ROUTE** | 路由评估、Fallback激活、Circuit Breaker熔断、可观测性报告 |
| **SCHEDULE** | 准入控制、出队调度、心跳、僵尸检测、抢占式调度 |
| **ACTIVATE** | Canary阶段切换、自动回滚、Feature Flag修改、健康检查 |

## 七层进化安全光谱

| 层级 | 进化程度 | 策略 |
|------|---------|------|
| L1 | 提示词优化 | 自动批准 |
| L2 | 知识结晶 | 自动批准 |
| L3 | 运行时自修改 | 安全且可控 |
| L4 | 编译时自修改 | 安全且可控 |
| L5 | 架构自搜索 | 成本感知+预算限制 |
| L6 | 开放式自进化 | 10%算力隔离探索 |
| L7 | 元级坍塌 | 禁止 |

## 六条不可逾越的红线

```
禁止修改 Human Gate
禁止绕过身份验证
禁止修改红线定义
禁止 L6+ 无审批进化
禁止修改审计日志
禁止超预算自我复制
```

## 6种故障注入模式

| 模式 | 测试目标 |
|------|---------|
| 网络分区 | Agent 间通信断裂下的降级行为 |
| 资源耗尽 | CPU/内存/存储极限下的熔断 |
| 数据损坏 | 输入数据被篡改后的检测与恢复 |
| 上下文投毒 | 恶意提示词注入的防御 |
| 目标漂移 | 任务目标被逐步偏离的检测 |
| 金丝雀令牌泄露 | 敏感凭证外泄的阻断 |

## 模式

- **独立运行**：完整 Agent 集群，无需依赖其他模块
- **组合模式**：MAREF + Skillos，通过 Men0 Protocol 互操作

## 核心指标

| 指标 | 公式/要求 |
|------|----------|
| ATLAS 效益 | `quality / (cost × time)`，低于 baseline 80% 触发优化 |
| GEPA 评估 | 静态分析+模拟执行+模式匹配（35x RL 效率） |
| Recovery Rate | > 99% |

## 操作接口

### 创建 Agent 集群
```
maref cluster create --name <name> --agents <count> --strategy he_tu
```

### 故障注入
```
maref fault inject --mode <network_partition|resource_exhaustion|...> --target <agent_id>
```

### 进化安全审查
```
maref evolution audit --level <L1-L7> --agent-id <id> --approval human
```

## 参考文档
- 核心方案：MAREF-v0.2.0-全量工程实施方案.md
- 生态认知：Athena生态全域认知系统文档.md (3.2节)
- 深度审计：003-maref-深度审计.md
- 河图策略：openclaw/wiki/ARCHITECTURE.md
