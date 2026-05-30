---
name: github-platform
description: "GitHub平台集成技能包 — 仓库管理、代码提交、Issue/PR管理、自动化工作流"
version: "1.0.0"
user-invocable: true
---

# GitHub 平台集成

## 触发条件
- 用户提到 GitHub 相关操作（仓库、提交、PR、Issue、CI/CD）
- 用户使用 gh CLI 命令
- 用户需要管理 frankiehot-tech 组织的仓库

## 执行步骤

### 1. 仓库管理
```bash
# 列出组织仓库
gh repo list frankiehot-tech

# 创建新仓库
gh repo create frankiehot-tech/<repo-name> --private --description "<desc>"

# 克隆仓库
gh repo clone frankiehot-tech/<repo-name>
```

### 2. 代码提交
```bash
# 智能提交（自动生成 commit message）
git add -A && git commit -m "<type>: <description>"

# 推送前安全检查（自动触发 pre_push hook）
git push origin <branch>
```

### 3. Issue/PR 管理
```bash
# 创建 Issue
gh issue create --title "<title>" --body "<body>" --label "<label>"

# 创建 PR
gh pr create --title "<title>" --body "<body>" --base main --head <branch>

# 审查 PR
gh pr review <number> --approve --body "<review>"
```

### 4. CI/CD 监控
```bash
# 查看工作流运行状态
gh run list --limit 5

# 查看特定运行详情
gh run view <run-id>

# 重新运行失败的工作流
gh run rerun <run-id>
```

### 5. 安全配置
```bash
# 启用 Dependabot
gh api repos/frankiehot-tech/<repo>/vulnerability-alerts -X PUT

# 扫描密钥泄露
trufflehog filesystem <path>
```

## 输出格式
- 操作结果：成功/失败 + 详情
- CI 状态：运行中/通过/失败
- 安全扫描：发现/未发现漏洞

## 配置
- 用户名: frankiehot-tech
- 工具: gh CLI, git, trufflehog
- 智能提交: 启用
- 默认工作流: 启用
