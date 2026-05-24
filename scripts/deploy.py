#!/usr/bin/env python3
"""deploy.py — 部署脚本

Phase 5.4: 部署方案

用法:
    python scripts/deploy.py --dry-run          # 预览部署操作
    python scripts/deploy.py --confirm          # 执行部署
    python scripts/deploy.py --skip-tests       # 跳过测试（不推荐）

部署步骤:
    1. 预部署验证（测试、安全扫描）
    2. 数据库迁移
    3. 记录部署版本
    4. 重启服务
    5. 健康检查
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skillos.version import get_version, get_version_manager

logger = logging.getLogger("deploy")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_command(cmd: list[str], description: str, dry_run: bool = False) -> bool:
    """运行 shell 命令。"""
    cmd_str = " ".join(cmd)
    if dry_run:
        logger.info("[DRY-RUN] Would run: %s", cmd_str)
        return True

    logger.info("Running: %s", cmd_str)
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            logger.debug(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("%s failed: %s", description, e)
        if e.stdout:
            logger.error("stdout: %s", e.stdout)
        if e.stderr:
            logger.error("stderr: %s", e.stderr)
        return False


def get_alembic_current_revision() -> str:
    """获取当前 Alembic revision。"""
    try:
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split()[0]
    except (subprocess.CalledProcessError, IndexError):
        return "unknown"


def run_tests(dry_run: bool = False) -> bool:
    """运行全量测试。"""
    return run_command(
        ["python", "-m", "pytest", "tests/", "-q", "--tb=short"],
        "Tests",
        dry_run,
    )


def run_security_scan(dry_run: bool = False) -> bool:
    """运行安全扫描。"""
    ok = True
    ok &= run_command(["bandit", "-r", "skillos/", "-q"], "Bandit scan", dry_run)
    ok &= run_command(["pip-audit"], "pip-audit", dry_run)
    return ok


def run_migrations(dry_run: bool = False) -> bool:
    """执行数据库迁移。"""
    return run_command(["alembic", "upgrade", "head"], "DB migration", dry_run)


def record_deployment(dry_run: bool = False) -> bool:
    """记录部署版本。"""
    if dry_run:
        logger.info("[DRY-RUN] Would record deployment version %s", get_version())
        return True

    try:
        mgr = get_version_manager()
        mgr.record_deployment(
            version=get_version(),
            alembic_revision=get_alembic_current_revision(),
            deployed_by="deploy-script",
            notes="Automated deployment",
        )
        logger.info("Deployment recorded: %s", get_version())
        return True
    except Exception as e:
        logger.error("Failed to record deployment: %s", e)
        return False


def health_check(dry_run: bool = False) -> bool:
    """健康检查。"""
    return run_command(
        ["python", "-m", "pytest", "tests/test_e2e.py", "-q", "--tb=short"],
        "Health check (E2E tests)",
        dry_run,
    )


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="SkillOS Deployment Tool")
    parser.add_argument("--dry-run", action="store_true", help="Preview deployment without executing")
    parser.add_argument("--confirm", action="store_true", help="Confirm and execute deployment")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test execution (not recommended)")
    parser.add_argument("--skip-security", action="store_true", help="Skip security scan (not recommended)")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        parser.print_help()
        print("\nError: Must specify --dry-run or --confirm")
        return 1

    logger.info("=" * 50)
    logger.info("SKILLOS DEPLOYMENT")
    logger.info("Version: %s", get_version())
    logger.info("Mode: %s", "DRY-RUN" if args.dry_run else "LIVE")
    logger.info("=" * 50)

    # Step 1: 预部署验证
    if not args.skip_tests:
        if not run_tests(args.dry_run):
            logger.error("Deployment aborted: tests failed")
            return 1

    if not args.skip_security:
        if not run_security_scan(args.dry_run):
            logger.error("Deployment aborted: security scan failed")
            return 1

    # Step 2: 数据库迁移
    if not run_migrations(args.dry_run):
        logger.error("Deployment aborted: migration failed")
        return 1

    # Step 3: 记录部署版本
    if not record_deployment(args.dry_run):
        logger.error("Deployment aborted: failed to record deployment")
        return 1

    # Step 4: 健康检查
    if not health_check(args.dry_run):
        logger.error("Deployment warning: health check failed")
        # 健康检查失败不中止部署，但发出警告

    logger.info("=" * 50)
    if args.dry_run:
        logger.info("DRY-RUN completed. No changes were made.")
    else:
        logger.info("Deployment completed successfully!")
    logger.info("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
