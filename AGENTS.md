# AGENTS.md — AI Agent Context for SkillOS

> **上位法**: 本文件受 [SkillOS 治理框架](GOVERNANCE.md) 约束。冲突时以治理框架为准。
> **泄密预防**: 本仓库不得包含 T3/T2 级内容（路径/Key/IP/时间戳）。

## Project Overview
- **名称**: SkillOS (Skill Operating System)
- **定位**: 技能操作系统，Agent 技能调度与编排
- **技术栈**: Python 3.10+
- **开源协议**: AGPL-3.0

## Release Gate

发布门禁见 `docs/release-gate.md`（10 项精简标准）。

验证命令: `python scripts/verify_distribution.py && python scripts/arch_check.py && python scripts/verify_kb_sync.py`

## Architecture

实际架构见 `ARCHITECTURE.md`。

## 治理合规检查清单

每次提交前应确认：

- [ ] 无 T3/T2 级内容（路径/Key/IP/时间戳）
- [ ] `git remote -v` 为授权远程
- [ ] pre-push hook 已就位
