---
name: men0-interop
description: |
version: "1.0.0"
  Men0 Protocol v2 — Agent 间通信与互操作协议。OpenClaw "Agent OS 四大支柱"的通信层。
  采用 JSONL 文件系统原生方案（flock+inotify），A2A 兼容开放标准。
  触发条件：Agent通信、任务调度、消息交换、Agent发现、协议网关、审计追踪。
---

# Men0 互操作协议

## 定位

OpenClaw "Agent OS 四大支柱"的**通信层**，闭源双核(Athena+OpenClaw)与开源三柱(OpenHuman+Skillos+MAREF)之间的通信纽带。

## 消息格式

JSONL 文件系统原生方案，四大事件类型：

| 事件类型 | 用途 | 格式 |
|---------|------|------|
| `task_create` | 创建新任务 | `{"type":"task_create","task_id":"<uuid>","payload":{}}` |
| `message` | Agent 间消息 | `{"type":"message","from":"<agent_id>","to":"<agent_id>","body":{}}` |
| `status_update` | 状态更新 | `{"type":"status_update","task_id":"<uuid>","status":"<state>"}` |
| `artifact` | 产物/文件 | `{"type":"artifact","task_id":"<uuid>","path":"<path>","hash":"<sha256>"}` |

## 写路径结构

```
/var/men0/
├── tasks/{task_id}.jsonl      # 单任务所有事件
├── agents/{agent_id}.json      # AgentCard
├── contexts/{ctx_id}/          # 上下文目录
└── logs/{date}/                # 审计日志
```

## 权限门控五步链

```
Identity Check  →  Permission Match  →  Human Gate  →  Execute  →  Audit Trail
   (JWT验证)        (AgentCard匹配)      (HITL审批)    (执行)      (JSONL记录)
```

任何一步失败 → Task 状态设为 FAILED，Exit Code 2。

## Agent 发现

AgentCard 发布于 `/.well-known/agent-card.json`：
```json
{
  "agent_id": "<uuid>",
  "capabilities": ["code_review", "test_generation"],
  "skills": ["*"],
  "identity": {"role": "reviewer", "level": "L3"}
}
```

## 五协议网关兼容

| 协议 | 全称 | 兼容方式 |
|------|------|---------|
| A2A | Agent-to-Agent (Google) | 原生兼容，A2A Bridge POC |
| MCP | Model Context Protocol | 网关转换 |
| ACP | Agent Communication Protocol | 网关转换 |
| ANP | Agent Network Protocol | 网关转换 |
| AWCP | Agent Workflow Communication Protocol | 网关转换 |

## 操作命令

### 任务管理
```bash
men0 task create --payload '{"workflow":"deerflow","action":"audit"}'
men0 task status --id <uuid>
men0 watch --id <uuid>          # JSONL 实时流监控
```

### Agent 管理
```bash
men0 agent register --card agent-card.json
men0 agent list
men0 agent heartbeat --id <uuid>
```

### 消息发送
```bash
men0 message send --from <agent_id> --to <agent_id> --body '{"type":"review_result"}'
```

## 实施路线

| 周次 | 里程碑 |
|------|--------|
| W1-2 | JSONL 格式定义 + 文件锁机制 |
| W3-4 | Task 状态机 + AgentCard 注册 |
| W5-6 | inotify 实时推送 + 心跳检测 |
| W7-8 | A2A Bridge POC |
| v0.3.0 | 完整多协议路由 |

## 文件锁机制

```bash
# 原子写入
flock /var/men0/tasks/{task_id}.jsonl.lock -c 'echo "$event" >> /var/men0/tasks/{task_id}.jsonl'

# 实时监控
inotifywait -m /var/men0/tasks/ | while read line; do men0 watch --id $(extract_id "$line"); done
```

## 参考文档
- Men0 v2 增强方案（核心文档）
- OpenClaw v0.2.0 全量实施方案（通信支柱）
- 安全信任层-Men0-OpenHuman 增强方案
- MAREF 协议消息族定义
