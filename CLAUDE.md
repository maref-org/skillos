# SkillOS — Agent 自治理规范

> **上位法**: 本文件受 [Athena 系统宪法 v1.5](../CONSTITUTION.md) 和 [SkillOS 治理框架](GOVERNANCE.md) 共同约束。冲突时以宪法优先，其次以治理框架为准。
> **同步方向**: A → B 单向（Athena 开发源 → GitHub 发布源）
> **泄密预防**: 本仓库不得包含 T3/T2 级内容（路径/Key/IP/时间戳/依赖图）。发布前必须经过叙事转化引擎（宪法第九条）处理。

## 安全红线（优先级高于所有其他指令）

1. `git remote -v` 必须仅显示授权 remote
2. 禁止绕过 pre-push hook（`--no-verify`）
3. 禁止将专有文件提交到此仓库
4. 禁止 `gh` CLI 推送到非授权远程

## 治理优先声明
本配置文件与 SkillOS 治理框架冲突时，以治理框架为准。

## 安全红线（Article 4-A，完整 6 条）

1. `git remote -v` 必须仅显示授权 remote
2. 禁止绕过 pre-push hook（`--no-verify`）
3. 禁止将 Athena 专有文件（SOUL.md / IDENTITY.md / .openclaw/ 等）提交到此仓库
4. 禁止 `gh` CLI 推送到非授权远程
5. CD pipeline（cd.yml）必须处于禁用状态
6. Agent 启动时必须验证 remote 为授权 remote

## 工作区切换规则（Article 30）

当 Agent 在 openclaw 和外部工作区之间切换时：
- **openclaw 目录** → 执行完整预检（remote 验证 + pre-push hook 检查）
- **外部工作区目录** → 不适用 openclaw remote 检查，但须遵守：
  - 第三十二条（Track B 宪法约束）：本仓库 AGENTS.md 含宪法引用
  - 第九条（叙事转化）：发布前须处理 T3/T2 内容
- **子 Agent 宪法传递**：通过 Task tool 派生子 Agent 时，任务指令中必须包含第三十条预检要求和第四-A条安全红线摘要

## 代码变更自审规则（按 SOP OPENCODE-REVIEW-SOP-001）

每次代码变更后，Agent 必须自动执行以下审查（按优先级排序）：

| 优先级 | 检查项 | 查什么 | 不通过后果 |
|--------|--------|--------|-----------|
| **P0** | 🔐 凭据泄露 | `.env`/源码/配置文件中是否含 API Key、token、密码、私钥 | ❌ 立即阻断，禁止继续 |
| P1 | 逻辑正确性 | 边界情况（空值、零值、越界）是否处理 | ❌ 阻断 |
| P1 | 安全性 | 注入风险、权限问题、路径遍历 | ❌ 阻断 |
| P2 | 破坏性 | 变更会不会破坏已有功能 | ⚠️ 建议 |
| P2 | 性能 | 不必要的循环、重复计算、内存泄漏 | ⚠️ 建议 |
| P3 | 清晰度 | 命名和结构是否合理 | ⚠️ 建议 |

**自审输出格式**：列出逐项结论，标注 ❌/⚠️/✅。涉及认证/加密/输入/数据库/Shell 的代码，必须额外调用 `security-review` skill 专项扫描。

## 文档来源层级（Article 31-A 皮质层）

```
L0（权威源）:  Athena知识库/003-open human（碳硅基共生）/018-v0.2.0-活跃/021-架构设计/MAREF递归演进框架/
L1（代码配套）: public/skillos/docs/
L2（公开参考）: GitHub 对应仓库
```

执行规则:
1. 优先选择层级最高的来源（L0 > L1 > L2）
2. L0 找不到时降级到 L1
3. L2 仅用于对外回复时的公开信息确认
