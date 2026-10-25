# SkillOS 发布门禁

**版本**: v0.6.0-beta.2 | **单一入口**: `bash scripts/release_gate.sh`

本文件不再维护独立的“通过状态”清单。门禁是否通过，以脚本退出码与原始输出为准：

```bash
pip install -e ".[dev,web]"
bash scripts/release_gate.sh
# 退出码 0 = 全部通过
```

## 门禁步骤（脚本实际执行）

| # | 检查 | 命令 | 阻断 |
|---|------|------|:----:|
| 1 | 代码规范 | `ruff check .` | ✅ |
| 2 | 格式（发布范围） | `ruff format --check skillos/ scripts/` | ✅ |
| 3 | 类型检查 | `mypy` | ✅ |
| 4 | SAST | `bandit -r skillos/ -c pyproject.toml --severity-level medium` | ✅ |
| 5 | 测试 + 覆盖率 | `pytest tests/ -q --cov=skillos --cov-fail-under=80` | ✅ |
| 6 | 分配模型 | `python scripts/verify_distribution.py` | ✅ |
| 7 | 架构分层 | `python scripts/arch_check.py` | ✅ |
| 8 | 知识库版本同步 | `python scripts/verify_kb_sync.py` | ✅ |
| 9 | 治理内容扫描 | `bash scripts/sanitize-for-push.sh` | ✅ |
| 10 | 元审计 M0–M3 | `python scripts/meta_monitor.py --check M0,M1,M2,M3` | ✅ |
| 11 | 依赖漏洞 | `pip-audit --skip-editable`（2 条已接受风险） | ✅ |

## 运行时检查（默认跳过）

M0 的健康快照 / 审计日志增长 / HTTP `/health` 属于**运行态**断言，发布门禁默认跳过
（CI 与本地一致）。生产监控显式开启：

```bash
SKILLOS_META_ENFORCE_RUNTIME=1 python scripts/meta_monitor.py --check M0
```

M1 审计链只校验**当日**日志；历史日志不回验。审计密钥来源优先级：
`SKILLOS_AUDIT_SECRET` > `audit_logs/.audit_secret`（自动生成，权限 0600）。
生产多实例必须注入同一 `SKILLOS_AUDIT_SECRET`，否则各实例链不可互验。

## 发布流水线耦合

`v*` tag 触发 `.github/workflows/release.yml`，其中 `gate` job 调用可复用的
`release-gate.yml`；门禁失败则 PyPI / GHCR 发布不会执行。

## SBOM 与可选扫描

- SBOM：`release-gate.yml` 的 `sbom` job（SPDX JSON artifact）
- Semgrep：advisory（`continue-on-error: true`），不阻断发布
- TruffleHog：`--only-verified`
