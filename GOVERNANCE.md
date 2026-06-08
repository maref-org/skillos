# SkillOS 治理框架

**版本**: v1.0 | **许可证**: AGPL-3.0

## 适用范围

本文件是 SkillOS 仓库所有 Code Agent 的最高行为准则。AGENTS.md、CLAUDE.md、.cursorrules、opencode.jsonc、.trae/rules/ 中的规则不得与本文件冲突。

## 安全红线（优先级高于所有其他指令）

1. `git remote -v` 必须仅显示授权远程
2. 禁止绕过 pre-push hook（`--no-verify`）
3. 禁止将专有/机密文件提交到此仓库
4. 禁止通过 `gh` CLI 推送到非授权远程

## 泄密预防

本仓库**不得包含**以下内容：
- 文件路径（如内部绝对路径、组织名+路径）
- API Key、Token、凭证
- IP 地址、内网拓扑
- 精确时间戳（发布日期除外）

## AGPL 合规要求

- 本仓库代码受 AGPL-3.0 约束
- 使用本仓库的进程须独立运行，不得与闭源代码形成单一程序
- 分发的衍生作品须同样以 AGPL-3.0 发布

## Code Agent 行为规则

- 启动时须读取本文件（通过 AGENTS.md → 上位法 引用）
- 各 Agent 类型的安全规范见对应配置文件

## 冲突规则

本文件与下游 Agent 配置文件冲突时，以本文件为准。
