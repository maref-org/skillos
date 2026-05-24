---
name: obsidian-vault
description: |
  通过 Obsidian CLI 操作知识库。用于检索笔记、创建/追加内容、管理属性和任务。
  触发关键词：obsidian、笔记、知识库、vault、记录、检索、wiki、每日笔记
version: "1.0.0"
sla:
  target_success_rate: 0.96
  max_latency_ms: 3000
changelog:
  - version: "1.0.0"
    date: "2026-05-06"
    changes: "Standardized frontmatter, added version, SLA, and changelog"
---

# Obsidian Vault Skill

## 前置条件
- Obsidian 桌面端必须运行（IPC 依赖）
- CLI 已注册：`/Applications/Obsidian.app/Contents/MacOS/obsidian`
- 默认 Vault：通过 `--vault` 参数指定，或配置环境变量 `OBSIDIAN_VAULT_NAME`

## 核心操作

### 1. 检索知识库
```
obsidian search:context "{{query}}" --vault "<VAULT_NAME>"
```
用途：Agent 先检索再回答，实现 RAG。需在引号内转义特殊字符。

### 2. 创建笔记
```
obsidian create "{{title}}" --template "{{template}}" --vault "<VAULT_NAME>"
```
用途：按标准模板生成结构化笔记。

### 3. 追加到笔记
```
obsidian append "{{file_path}}" "{{content}}"
```

### 4. 属性管理
```
obsidian property get "{{file}}" "{{key}}"
obsidian property set "{{file}}" "{{key}}" "{{value}}"
```
优先使用此方式，避免直接写 frontmatter 破坏 YAML 格式。

### 5. 每日笔记
```
obsidian daily:path
obsidian daily
```

### 6. 任务管理
```
obsidian task list
obsidian task add "{{task}}"
obsidian task complete "{{task_id}}"
```

## 知识库结构

参考 `wiki/CROSS_PROJECT.md` 了解知识库的完整索引结构。
项目文档通过 Obsidian Vault 组织管理。

## 注意事项
- Obsidian 必须运行：确保 Mac mini / MacBook 上 Obsidian 保持运行
- 多 Vault：命令中通过 `--vault` 指定目标库
- 属性优先：尽量用 `property set/get` 而非直接文件操作
- 错误处理：检查命令返回码，处理 Obsidian 未运行的情况
- 文件路径：使用绝对路径或相对于 Vault 根目录的路径
