---
name: deerflow-pipeline
description: |
  DeerFlow v2 — Athena 战略大脑的工作流执行引擎。负责复杂任务的 DAG 分解、编排与执行。
  吸收 ByteDance DeerFlow 2.0 的八项核心能力，构建 L3-L7 完整工作流光谱。
  触发条件：工作流编排、DAG执行、任务分解、HITL审批、流水线设计、Recovery处理。
version: "1.0.0"
sla:
  target_success_rate: 0.93
  max_latency_ms: 10000
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes: "Standardized frontmatter, added version, SLA, and changelog"
---

# DeerFlow 流水线

## 八层完整能力栈

```
┌─────────────────────────────────────┐
│ 编排层   Symphony 轮询-声明协议       │
├─────────────────────────────────────┤
│ 规划层   Plan-and-Execute DAG        │
├─────────────────────────────────────┤
│ 执行层   ReAct 微观循环              │
├─────────────────────────────────────┤
│ 质量层   Reflexion 自我批判          │
├─────────────────────────────────────┤
│ 人机层   HITL 分级审批               │
├─────────────────────────────────────┤
│ 优化层   OptoPrime 节点自优化        │
├─────────────────────────────────────┤
│ 安全层   Dual-Helix 三轨治理         │
├─────────────────────────────────────┤
│ 记忆层   Workpad 外部化工作记忆      │
└─────────────────────────────────────┘
```

## 工作流光谱 (L3-L7)

| 层级 | 能力 | 说明 |
|------|------|------|
| L3 | 代码优先状态机 | 基础编排，Git版本控制 |
| L4 | CI/CD 集成 | 自动化测试+部署流水线 |
| L5 | 多Agent 编排 | 并行Sub-Agent委派 |
| L6 | 递归自优化 | OptoPrime节点级优化 |
| L7 | 全自主工作流 | 人类仅设定目标 |

## HITL 分级审批

| 级别 | 触发条件 | 审批方式 |
|------|---------|---------|
| **P0** | 安全关键操作（修改Human Gate、密钥轮换、L6+进化） | 同步阻断，强制人工审批 |
| **P1** | 预算敏感操作（成本超过阈值、外部API调用） | 异步通知 + 30s 自动放行 |
| **P2** | 常规操作（代码生成、测试运行、文档更新） | 仅日志记录，无需审批 |

## Task 状态机 (A2A 对齐)

```
pending → running → waiting_for_human → waiting_for_auth → done
                  ↘ error
```

## Symphony 轮询-声明协议

1. Agent 轮询 `WORKFLOW.md` 获取当前工作流定义
2. Agent CLAIM 一个待执行节点
3. HEARTBEAT 维持执行状态
4. 完成后更新节点状态 + 释放 CLAIM

## 操作接口

### 创建 DAG 工作流
```yaml
# workflow.yaml
name: code-review-pipeline
dag:
  - id: lint
    depends_on: []
    action: run_lint
  - id: test
    depends_on: [lint]
    action: run_tests
  - id: review
    depends_on: [test]
    action: llm_review
    hitl_level: P1
  - id: deploy
    depends_on: [review]
    action: deploy
    hitl_level: P0
```

### 执行命令
```bash
deerflow run --workflow workflow.yaml --target <repo_path>
deerflow status --run-id <uuid>
deerflow retry --run-id <uuid> --from-node test
```

### 加入 Obsidian 归档节点
```yaml
  - id: obsidian_log
    depends_on: [deploy]
    action: obsidian_log
    config:
      command: "obsidian append 'logs/deerflow.md' '{{run_summary}}'"
```

## 核心指标

| 指标 | 目标 |
|------|------|
| DAG 规模 | 50+ 节点稳定执行 |
| Recovery Rate | > 99% |
| HITL 延迟 | P0 < 60s, P1 < 30s |
| 并行度 | 按资源自动调优 |

## 典型任务生命周期

```
OpenHuman Dashboard 创建任务
  → Athena DeerFlow DAG 分解
    → OpenClaw Men0 v2 广播任务
      → Agent CLAIM 节点
        → ReAct Loop 执行
          → HITL 分级审批
            → 结果汇聚 + Obsidian 归档
```

## 与其他模块集成

| 模块 | 集成点 |
|------|--------|
| Men0 | Task 状态机对齐 A2A 规范 |
| MAREF | 故障注入测试 Recovery Rate |
| OpenHuman | HITL 审批通过 OpenHuman Dashboard |
| Obsidian | 自动归档到 Athena 知识库 |

## 参考文档
- Athena v0.2.0 方案（DeerFlow v2 核心定义）
- Agent智能工作流综合研究报告
- DeerFlow 2.0 类Agent架构增量升级方案
- 规划框架与人机协同编排 ReAct-HITL-KAIROS
