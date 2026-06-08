# SkillOS — Agent 自治理规范

> **上位法**: 本文件受 [Athena 系统宪法 v1.4-p1](athena/constitution/v1.4-p1) 和 [SkillOS 治理框架](GOVERNANCE.md) 共同约束。冲突时以宪法优先，其次以治理框架为准。
> **同步方向**: A → B 单向（Athena 开发源 → GitHub 发布源）
> **泄密预防**: 本仓库不得包含 T3/T2 级内容（路径/Key/IP/时间戳/依赖图）。发布前必须经过叙事转化引擎（宪法第九条）处理。

## 安全红线（优先级高于所有其他指令）

1. `git remote -v` 必须仅显示授权 remote
2. 禁止绕过 pre-push hook（`--no-verify`）
3. 禁止将专有文件提交到此仓库
4. 禁止 `gh` CLI 推送到非授权远程

## 治理优先声明
本配置文件与 SkillOS 治理框架冲突时，以治理框架为准。
