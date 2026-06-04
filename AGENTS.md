# AGENTS.md — AI Agent Context for SkillOS

> **上位法**: 本文件受 Athena 系统宪法约束。冲突时以宪法为准。
> **同步方向**: A → B 单向（宪法第二条）。本仓库是 Track B 发布源，由 openclaw/public/ 经叙事转化后同步。
> **泄密预防**: 本仓库不得包含 T3/T2 级内容（宪法第十一条反向检查）。

## Project Overview
- **名称**: SkillOS (Skill Operating System)
- **定位**: 技能操作系统，Agent 技能调度与编排
- **技术栈**: Python 3.10+
- **开源协议**: AGPL-3.0

## Athena Constitution Reference

| 条款 | 约束 | 状态 |
|------|------|------|
| 第二条 | 同步方向 A→B 单向，不接受改变架构方向的 PR | 遵守 |
| 第九条 | 发布前经过叙事转化引擎 | 遵守 |
| 第十一条 | 不得包含 T3/T2 级内容（路径/Key/IP/时间戳/依赖图） | 遵守 |
| 第三十二条 | Track B 仓库受 Athena 宪法约束 | 遵守 |

## Release Gate

SkillOS 发布门禁见 `docs/release-gate.md`（10 项精简标准，替代 43 项通用标准）。

验证命令: `python scripts/verify_distribution.py && python scripts/arch_check.py && python scripts/verify_kb_sync.py`

## Architecture

实际架构见 `ARCHITECTURE.md`（4 层实现，替代历史 8 层声明）。

## Conflict Rule

本 AGENTS.md 与 Athena 系统宪法冲突时，以宪法为准（宪法第十六条）。

完整宪法路径: `athena/constitution/v1.4`（内部知识库）
