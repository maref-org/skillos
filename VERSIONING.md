# SkillOS 版本号管理策略

## 版本号格式

采用 [Semantic Versioning 2.0.0](https://semver.org/lang/zh-CN/) 规范：

```
主版本号.次版本号.修订号[-预发布标识][+构建元数据]
```

示例：`0.3.0`, `0.4.0-beta`, `1.0.0+20260524`

## 版本号变更规则

| 变更类型 | 版本号变化 | 示例 | 触发条件 |
|----------|------------|------|----------|
| 重大更新 | 主版本号 +1 | `0.3.0` → `1.0.0` | 不兼容的 API 变更 |
| 功能更新 | 次版本号 +1 | `0.3.0` → `0.4.0` | 向下兼容的功能新增 |
| 问题修复 | 修订号 +1 | `0.3.0` → `0.3.1` | 向下兼容的问题修复 |
| 预发布 | 添加预发布标识 | `0.4.0-beta` | 功能完成但未稳定 |

## 版本号文件位置

| 文件 | 用途 | 更新时机 |
|------|------|----------|
| `pyproject.toml` | 项目元数据、PyPI 发布 | 每次版本变更 |
| `skillos/version.py` | 运行时版本查询 | 每次版本变更 |
| `CHANGELOG.md` | 变更历史记录 | 每次版本变更 |
| `docs/deployment.md` | 部署文档版本引用 | 每次版本变更 |
| `docs/ops.md` | 运维文档版本引用 | 每次版本变更 |
| `docker-compose.yml` | 容器镜像版本标签 | 每次版本变更 |

## Git 标签管理

### 标签格式

```bash
# 正式版本
git tag -a v0.3.0 -m "Release v0.3.0"

# 预发布版本
git tag -a v0.4.0-beta -m "Pre-release v0.4.0-beta"

# 构建版本
git tag -a v0.3.0+20260524 -m "Build v0.3.0 (2026-05-24)"
```

### 标签推送

```bash
# 推送单个标签
git push origin v0.3.0

# 推送所有标签
git push origin --tags
```

## 分支策略

```
main        ───────●─────────●─────────●─────────
                   ↑         ↑         ↑
                v0.3.0    v0.3.1    v0.4.0

develop     ──●──●──●──●──●──●──●──●──●──●──●──
                 ↑        ↑        ↑
              feature   feature   feature

release/0.4.0 ─────────────●────●────●─────────
                           ↑    ↑    ↑
                         beta  rc1  v0.4.0

hotfix/0.3.1 ─────────────────────●────●───────
                                  ↑    ↑
                                bug   v0.3.1
```

### 分支说明

| 分支 | 用途 | 保护规则 |
|------|------|----------|
| `main` | 生产代码 | 禁止直接推送，需 PR 合并 |
| `develop` | 开发集成 | 禁止直接推送，需 PR 合并 |
| `feature/*` | 功能开发 | 从 develop 创建，合并回 develop |
| `release/*` | 版本发布 | 从 develop 创建，合并到 main 和 develop |
| `hotfix/*` | 紧急修复 | 从 main 创建，合并到 main 和 develop |

## 发布流程

### 1. 准备发布

```bash
# 1. 从 develop 创建 release 分支
git checkout -b release/0.4.0 develop

# 2. 更新版本号
# - pyproject.toml
# - skillos/version.py
# - CHANGELOG.md
# - docs/deployment.md
# - docs/ops.md
# - docker-compose.yml

# 3. 提交版本号变更
git add .
git commit -m "chore(release): bump version to 0.4.0"
```

### 2. 预发布测试

```bash
# 1. 创建预发布标签
git tag -a v0.4.0-beta -m "Pre-release v0.4.0-beta"
git push origin v0.4.0-beta

# 2. 触发 CI/CD 测试
# GitHub Actions 会自动运行测试

# 3. 发现问题则修复
# 在 release/0.4.0 分支上修复
git commit -m "fix: resolve issue in beta"
```

### 3. 正式发布

```bash
# 1. 合并到 main
git checkout main
git merge --no-ff release/0.4.0 -m "Release v0.4.0"

# 2. 创建版本标签
git tag -a v0.4.0 -m "Release v0.4.0"
git push origin main --tags

# 3. 合并回 develop
git checkout develop
git merge --no-ff release/0.4.0 -m "Merge release v0.4.0 back to develop"
git push origin develop

# 4. 删除 release 分支
git branch -d release/0.4.0
git push origin --delete release/0.4.0
```

### 4. PyPI 发布

release.yml 工作流会自动触发：

```yaml
on:
  push:
    tags:
      - "v*"
```

## 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/) 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型说明

| 类型 | 说明 | 版本号影响 |
|------|------|------------|
| `feat` | 新功能 | 次版本号 +1 |
| `fix` | Bug 修复 | 修订号 +1 |
| `docs` | 文档变更 | 无 |
| `style` | 代码格式 | 无 |
| `refactor` | 代码重构 | 无 |
| `perf` | 性能优化 | 修订号 +1 |
| `test` | 测试相关 | 无 |
| `chore` | 构建/工具 | 无 |
| `security` | 安全修复 | 修订号 +1 |

### 示例

```bash
# 新功能
feat(kernel): add wasm sandbox execution support

# Bug 修复
fix(protocol): resolve HTTPS enforcement bypass

# 文档更新
docs(deployment): update Docker deployment guide

# 版本发布
chore(release): bump version to 0.4.0
```

## 版本支持策略

| 版本 | 状态 | 支持期限 |
|------|------|----------|
| 0.3.x | Active support | 2026-12-31 |
| 0.2.x | Maintenance | 2026-09-30 |
| < 0.2 | End of life | 已停止支持 |

## 回滚策略

### 1. 代码回滚

```bash
# 回滚到上一个版本
git revert HEAD

# 回滚到指定版本
git revert v0.3.0

# 强制回滚（谨慎使用）
git reset --hard v0.3.0
git push --force
```

### 2. 部署回滚

```bash
# 使用 rollback.py 脚本
python scripts/rollback.py --dry-run
python scripts/rollback.py --confirm

# 回滚到指定 revision
python scripts/rollback.py --to-revision abc123
```

### 3. 数据库回滚

```bash
# Alembic 回滚
alembic downgrade -1

# 回滚到指定版本
alembic downgrade abc123
```

## 检查清单

### 发布前检查

- [ ] 版本号已在所有文件中更新
- [ ] CHANGELOG.md 已更新
- [ ] 所有测试通过
- [ ] 安全扫描通过
- [ ] 文档已更新
- [ ] Docker 镜像可构建
- [ ] 数据库迁移已测试

### 发布后检查

- [ ] Git 标签已推送
- [ ] PyPI 包已发布
- [ ] Docker 镜像已推送
- [ ] 部署文档已更新
- [ ] 监控告警正常
- [ ] 健康检查通过
