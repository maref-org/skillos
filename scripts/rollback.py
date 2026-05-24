#!/usr/bin/env python3
"""rollback.py — 一键回滚脚本

Phase 5.2: 回滚机制

用法:
    python scripts/rollback.py --dry-run          # 预览回滚操作
    python scripts/rollback.py --confirm          # 执行回滚
    python scripts/rollback.py --to-revision abc  # 回滚到指定 revision

回滚步骤:
    1. 读取部署历史，确定上一个稳定版本
    2. Alembic 数据库降级到目标 revision
    3. 恢复功能开关状态
    4. 记录回滚事件到审计日志
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from skillos.version import VersionManager, get_version

logger = logging.getLogger("rollback")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_alembic_current_revision() -> str:
    """获取当前 Alembic revision。"""
    try:
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            check=True,
        )
        # 输出格式: "abc123 (head)"
        line = result.stdout.strip().splitlines()[0]
        return line.split()[0]
    except (subprocess.CalledProcessError, IndexError) as e:
        logger.error("Failed to get current alembic revision: %s", e)
        return "unknown"


def alembic_downgrade(target_revision: str, dry_run: bool = False) -> bool:
    """执行 Alembic 降级。"""
    if dry_run:
        logger.info("[DRY-RUN] Would run: alembic downgrade %s", target_revision)
        return True

    try:
        subprocess.run(
            ["alembic", "downgrade", target_revision],
            check=True,
        )
        logger.info("Alembic downgrade to %s completed", target_revision)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Alembic downgrade failed: %s", e)
        return False


def restore_feature_flags(flags: dict, dry_run: bool = False) -> None:
    """恢复功能开关状态。"""
    if not flags:
        return

    if dry_run:
        logger.info("[DRY-RUN] Would restore %d feature flags", len(flags))
        for name, state in flags.items():
            logger.info("  - %s: %s", name, state)
        return

    try:
        from skillos.feature_flags import FeatureFlagManager, FlagState, FlagType

        mgr = FeatureFlagManager()
        for name, config in flags.items():
            existing = mgr.get_flag(name)
            if existing is None:
                mgr.create_flag(
                    name=name,
                    flag_type=FlagType(config.get("type", "boolean")),
                    state=FlagState(config.get("state", "disabled")),
                    value=config.get("value"),
                )
            else:
                mgr.update_flag(
                    name=name,
                    state=FlagState(config.get("state", "disabled")),
                    value=config.get("value"),
                )
        logger.info("Restored %d feature flags", len(flags))
    except Exception as e:
        logger.error("Failed to restore feature flags: %s", e)


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="SkillOS Rollback Tool")
    parser.add_argument("--dry-run", action="store_true", help="Preview rollback without executing")
    parser.add_argument("--confirm", action="store_true", help="Confirm and execute rollback")
    parser.add_argument("--to-revision", type=str, help="Target Alembic revision")
    parser.add_argument("--state-dir", type=str, default="./.skillos/state", help="State directory")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm and not args.to_revision:
        parser.print_help()
        print("\nError: Must specify --dry-run, --confirm, or --to-revision")
        return 1

    version_mgr = VersionManager(state_dir=args.state_dir)

    # 获取回滚信息
    if args.to_revision:
        rollback_info = {
            "from_version": get_version(),
            "to_version": "unknown",
            "from_revision": get_alembic_current_revision(),
            "to_revision": args.to_revision,
            "feature_flags_to_restore": {},
        }
    else:
        rollback_info = version_mgr.prepare_rollback()
        if rollback_info is None:
            logger.error("No previous deployment found. Cannot rollback.")
            return 1

    # 显示回滚计划
    logger.info("=" * 50)
    logger.info("ROLLBACK PLAN")
    logger.info("=" * 50)
    logger.info("From version : %s", rollback_info["from_version"])
    logger.info("To version   : %s", rollback_info["to_version"])
    logger.info("DB revision  : %s -> %s", rollback_info["from_revision"], rollback_info["to_revision"])
    logger.info("Feature flags: %d to restore", len(rollback_info.get("feature_flags_to_restore", {})))
    logger.info("=" * 50)

    if args.dry_run:
        logger.info("DRY-RUN mode: No changes will be made.")
        alembic_downgrade(rollback_info["to_revision"], dry_run=True)
        restore_feature_flags(rollback_info.get("feature_flags_to_restore", {}), dry_run=True)
        return 0

    if args.confirm or args.to_revision:
        logger.warning("Executing rollback...")

        # 1. 降级数据库
        if not alembic_downgrade(rollback_info["to_revision"], dry_run=False):
            logger.error("Rollback aborted due to DB downgrade failure.")
            return 1

        # 2. 恢复功能开关
        restore_feature_flags(rollback_info.get("feature_flags_to_restore", {}), dry_run=False)

        # 3. 记录回滚
        version_mgr.confirm_rollback(rollback_info)

        logger.info("Rollback completed successfully.")
        logger.info("Current version: %s", rollback_info["to_version"])
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
