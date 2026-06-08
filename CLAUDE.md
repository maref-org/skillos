# SkillOS — Agent 自治理规范

> **上位法**: 本文件受 [SkillOS 治理框架](GOVERNANCE.md) 约束。冲突时以治理框架为准。

## 安全红线（优先级高于所有其他指令）

1. `git remote -v` 必须仅显示授权 remote
2. 禁止绕过 pre-push hook（`--no-verify`）
3. 禁止将专有文件提交到此仓库
4. 禁止 `gh` CLI 推送到非授权远程

## 治理优先声明
本配置文件与 SkillOS 治理框架冲突时，以治理框架为准。
