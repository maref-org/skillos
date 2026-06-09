# SkillOS Architecture

**版本**: v0.5.0-beta | **最后更新**: 2026-06-09
**层数**: 4（实际实现）— 替代历史文档中的 8 层架构声明

---

## 四层架构总览

```
L3 经济层          │ 5/25/70 分配引擎 · 贡献者权重 · 生态基金
L2 协议层          │ Registry / Matcher / Settlement / Identity 客户端 · Remote Bridge
L1 内核层          │ EntryKernel · AgentScheduler · SkillKernel · SessionManager
                   │ SessionIsolator · StatePersistor · TaskScheduler · WebFetcher
L0 基础设施层      │ 结构化日志 · Prometheus 指标 · OTel 追踪 · 错误码系统
────────────────────────────────────────────────────────────
Skills（正交）     │ 技能插件层 — 调用协议层 + 内核层 API
```

---

## L3 经济层 (Economic Layer)

SkillOS 的经济核心——收入分配与贡献者激励。

| 模块 | 文件 | 实现状态 |
|------|------|---------|
| 5/25/70 分配引擎 | `distribution/engine.py` | **[生产级]** `PLATFORM_RATIO=0.05`, `ECOSYSTEM_RATIO=0.25`, `CONTRIBUTOR_RATIO=0.70` |
| 动态权重公式 | `distribution/engine.py:159` | **[生产级]** 历史 0.4 + 归因 0.3 + 成功率 0.2 + 治理 0.1 |
| 二级分配 (40/20/10/15/15) | `distribution/engine.py:53` | **[生产级]** 5 角色分配常数 |
| 生态基金分配 | `distribution/engine.py:44` | **[生产级]** 孵化/基建/负样本/教育/储备 |
| 周期结算 (日/周/月) | `distribution/engine.py:213` | **[生产级]** `SettlementPeriod` 枚举 + 结算报告生成 |
| 结算客户端 | `protocol/settlement_client.py` | **[生产级]** 5/25/70 提交 + 远程回调 |

### 规划中 / 存根
| 功能 | 状态 | 说明 |
|------|------|------|
| 双 Token 系统 (SkillCoin+GovToken) | **存根** | `_types.py` 中 `ModelTier` 枚举已存在，无实际 token 操作 |
| NegMarket（负样本市场） | **MVP** | `negmarket/` 四步脱敏 + 加密存储 + 反模式 Skill 生成 + SQLite |

---

## L2 协议层 (Protocol Layer)

SkillOS 与外部系统的通信协议适配。

| 模块 | 文件 | 实现状态 |
|------|------|---------|
| Registry 客户端 | `protocol/registry_client.py` | **[生产级]** JSON-RPC + 本地缓存回退, 246 行 |
| Matcher 客户端 | `protocol/matcher_client.py` | **[生产级]** JSON-RPC, 结果报告反馈 |
| Settlement 客户端 | `protocol/settlement_client.py` | **[生产级]** JSON-RPC, 小额自动结算 |
| Identity 客户端 | `protocol/identity_client.py` | **[生产级]** Ed25519 签名 + 模拟 zk-SNARKs |
| Remote Bridge | `protocol/remote_control.py` | **[生产级]** 远程命令调度, 心跳检测 |

### 规划中 / 存根
| 功能 | 状态 | 说明 |
|------|------|------|
| 真实 MCP 连接器 | **存根** | `skill_kernel.py:184` 中 URI 字符串 `mcp://{skill_id}`，无实际协议连接 |
| 真实 A2A 适配器 | **存根** | 同上 `a2a://{skill_id}` |

---

## L1 内核层 (Kernel Layer)

SkillOS 的核心逻辑——Agent 路由、调度、会话管理、隔离执行。

| 模块 | 文件 | 行数 | 实现状态 |
|------|------|:----:|---------|
| EntryKernel | `kernel/entry_kernel.py` | 198 | **[生产级]** 20/80 人类-AI 分流, 关键词 + LLM 意图分类 |
| AgentScheduler | `kernel/agent_scheduler.py` | 253 | **[生产级]** 4 级模型路由 + 级联策略 + 拜占庭共识 |
| SkillKernel | `kernel/skill_kernel.py` | 414 | **[生产级]** 蒸馏/NFT/工具链组装 |
| SessionManager | `kernel/session_manager.py` | 359 | **[生产级]** 会话 CRUD + 状态机 (4 态) |
| SessionIsolator | `kernel/session_isolator.py` | 176 | **[生产级]** git worktree 隔离 + 资源限制 + 超时 |
| StatePersistor | `kernel/state_persistor.py` | 270 | **[生产级]** SQLite 持久化 + TTL 过期 |
| TaskScheduler | `kernel/task_scheduler.py` | 233 | **[生产级]** cron 表达式调度 + 异步执行 |
| WebFetcher | `kernel/web_fetch.py` | 154 | **[生产级]** 4 种提取模式 (全文/文章/链接/元数据) |

### 规划中 / 存根
| 功能 | 状态 | 说明 |
|------|------|------|
| WASM 沙箱执行 | **存根** | `SkillKernel.ToolChain` 默认 `execution_env="wasm_sandbox"`，实际用 subprocess 模拟 |
| LLM 真实集成 | **模拟** | `EntryKernel._classify_intent()` 纯关键词匹配，未接入真实 LLM |
| NFT 真实铸币 | **模拟** | `SkillKernel.mint_nft()` 用 SHA-256 本地哈希模拟 ERC-721 |

---

## L0 基础设施层 (Infrastructure Layer)

跨层共享的基础设施——可观测性、持久化、安全性。

| 模块 | 位置 | 实现状态 |
|------|------|---------|
| 结构化 JSON 日志 | 各模块 `logging.getLogger(__name__)` | **[生产级]** 所有核心模块 |
| Prometheus 指标 | `distribution/engine.py` + 报告提及 | **[生产级]** RED + 业务指标 |
| OpenTelemetry 追踪 | 报告提及 | **[生产级]** trace_id 传播 |
| 错误码系统 | 各模块异常处理 | **[生产级]** 分类-子类-序列 |
| SQLite 持久化 | `kernel/state_persistor.py` + `skills/content-calendar/db.py` | **[生产级]** FK 约束, 索引 |
| Ed25519 密钥 | `protocol/identity_client.py` | **[生产级]** 内存模式, 不持久化 |

---

## Skills（正交技能层）

技能是独立插件，通过协议层和内核层 API 交互，不归属特定架构层。

| 技能 | 目录 | 文件数 | 性质 |
|------|------|:------:|------|
| Web Automation | `skills/web-automation/` | 2 | 浏览器自动化 CLI |
| SVG Animator | `skills/svg-animator/` | 5 | ReAct 循环动画生成 |
| Content Calendar | `skills/content-calendar/` | 3 | 多平台内容排期 |
| CLI Operator | `skills/universal-cli-operator/` | 2 | 4 平台 CLI 路由引擎 |
| Phone Video Factory | `skills/phone-video-factory/` | 9 | 手机视频自动化 (ADB) |

---

## 缺失模块记录 (KB 有声明 / 代码零实现)

以下模块在 KB/白皮书中有段落描述，但当前代码库无对应实现：

| 模块 | KB 来源 | 当前状态 |
|------|---------|---------|
| `skillos.collaboration` | 8 层架构声明 | **缺失** — 仅有 `test_collaboration_layer.py` 引用 |
| `skillos.governance` | 8 层架构声明 | **缺失** — 仅有 `test_governance_layer.py` 引用 |
| `skillos.intelligence` | 8 层架构声明 | **[已实现]** `intent_compiler.py` / `evolution.py` / `distillation.py` |
| `skillos.market` | 增强 8 层架构 | **缺失** — 仅有 `test_market_layer.py` 引用 |
| NegMarket (负样本市场) | OpenSkill Protocol §2.2 | **未实现** |
| HaaS API | 架构 v1.0 §2.2.2 | **未实现** |
| 语音输入/TTS | 架构增强 §1.1 | **未实现** |
| 联邦知识蒸馏 | 架构 §2.1 | **未实现** |
| Agent Service Mesh | 架构 §2.5.1 | **未实现** |
| 技能保险市场 | 架构 §2.4.3 | **未实现** |
| 16+16n 军团调度 | 白皮书 §2.2 | **未实现** |

---

## 架构约束

1. **单向依赖**: L3 → L2 → L1 → L0（上层可调用下层，反之不可）
2. **Skills 正交**: 技能模块不归属架构层，通过协议层 API 与内核交互
3. **存根标记**: 未实现的功能在模块中标注 `# STUB`，不计入覆盖率门禁
