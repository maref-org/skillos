#!/usr/bin/env python3
"""backup.py — 自动化备份脚本

用法:
    python scripts/backup.py --db              # 备份数据库
    python scripts/backup.py --audit           # 备份审计日志
    python scripts/backup.py --all             # 全量备份
    python scripts/backup.py --restore <path>  # 恢复备份

备份策略:
    - 数据库: SQLite 直接复制 / PostgreSQL 使用 pg_dump
    - 审计日志: 按日期归档压缩
    - 保留最近 30 天备份，自动清理旧备份
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("backup")

DEFAULT_BACKUP_DIR = Path("./.skillos/backups")
RETENTION_DAYS = 30


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def ensure_backup_dir() -> Path:
    backup_dir = DEFAULT_BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_db_path() -> str:
    """从环境变量或默认路径获取数据库文件路径。"""
    db_url = os.getenv("SKILLOS_DATABASE_URL", "sqlite:///./skillos.db")
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "")
    return ""


def backup_db(backup_dir: Path) -> Path | None:
    """备份数据库文件。"""
    db_path = get_db_path()
    if not db_path:
        logger.info("PostgreSQL detected, using pg_dump...")
        return backup_postgres(backup_dir)

    db_file = Path(db_path)
    if not db_file.exists():
        logger.error("Database file not found: %s", db_file)
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"skillos_db_{timestamp}.db"

    try:
        shutil.copy2(db_file, backup_file)
        logger.info("Database backed up to: %s", backup_file)
        return backup_file
    except OSError as exc:
        logger.error("Database backup failed: %s", exc)
        return None


def backup_postgres(backup_dir: Path) -> Path | None:
    """使用 pg_dump 备份 PostgreSQL。"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"skillos_db_{timestamp}.sql"

    db_url = os.getenv("SKILLOS_DATABASE_URL", "")
    try:
        subprocess.run(
            ["pg_dump", db_url, "-f", str(backup_file)],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("PostgreSQL backed up to: %s", backup_file)
        return backup_file
    except subprocess.CalledProcessError as e:
        logger.error("pg_dump failed: %s", e.stderr)
        return None
    except FileNotFoundError:
        logger.error("pg_dump not found. Please install PostgreSQL client tools.")
        return None


def backup_audit(backup_dir: Path) -> Path | None:
    """备份并压缩审计日志。"""
    audit_dir = Path(os.getenv("SKILLOS_AUDIT_DIR", "./audit_logs"))
    if not audit_dir.exists():
        logger.warning("Audit log directory not found: %s", audit_dir)
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = backup_dir / f"audit_logs_{timestamp}.tar.gz"

    try:
        subprocess.run(
            ["tar", "-czf", str(archive_name), "-C", str(audit_dir.parent), audit_dir.name],
            check=True,
        )
        logger.info("Audit logs backed up to: %s", archive_name)
        return archive_name
    except subprocess.CalledProcessError as exc:
        logger.error("Audit backup failed: %s", exc)
        return None


def cleanup_old_backups(backup_dir: Path) -> int:
    """清理超过保留期的旧备份。"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed = 0

    for item in backup_dir.iterdir():
        if not item.is_file():
            continue
        try:
            stat = item.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                item.unlink()
                removed += 1
                logger.debug("Removed old backup: %s", item.name)
        except OSError as exc:
            logger.warning("Failed to remove %s: %s", item.name, exc)

    if removed:
        logger.info("Cleaned up %d old backups (retention: %d days)", removed, RETENTION_DAYS)
    return removed


def restore_db(backup_path: Path) -> bool:
    """从备份恢复数据库。"""
    if not backup_path.exists():
        logger.error("Backup file not found: %s", backup_path)
        return False

    db_path = get_db_path()
    if not db_path:
        # PostgreSQL restore
        db_url = os.getenv("SKILLOS_DATABASE_URL", "")
        try:
            subprocess.run(
                ["psql", db_url, "-f", str(backup_path)],
                check=True,
            )
            logger.info("PostgreSQL restored from: %s", backup_path)
            return True
        except subprocess.CalledProcessError as e:
            logger.error("psql restore failed: %s", e.stderr)
            return False

    # SQLite restore
    db_file = Path(db_path)
    try:
        # 先备份当前数据库
        if db_file.exists():
            current_backup = db_file.with_suffix(
                f".db.pre_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            )
            shutil.copy2(db_file, current_backup)
            logger.info("Current database backed up to: %s", current_backup)

        shutil.copy2(backup_path, db_file)
        logger.info("Database restored from: %s", backup_path)
        return True
    except OSError as exc:
        logger.error("Database restore failed: %s", exc)
        return False


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description="SkillOS Backup Tool")
    parser.add_argument("--db", action="store_true", help="Backup database")
    parser.add_argument("--audit", action="store_true", help="Backup audit logs")
    parser.add_argument("--all", action="store_true", help="Full backup (db + audit)")
    parser.add_argument("--restore", type=str, help="Restore database from backup file")
    parser.add_argument("--backup-dir", type=str, default=str(DEFAULT_BACKUP_DIR), help="Backup directory")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    if args.restore:
        return 0 if restore_db(Path(args.restore)) else 1

    if not args.db and not args.audit and not args.all:
        parser.print_help()
        return 1

    do_db = args.db or args.all
    do_audit = args.audit or args.all

    success = True

    if do_db:
        if backup_db(backup_dir) is None:
            success = False

    if do_audit:
        if backup_audit(backup_dir) is None:
            success = False

    cleanup_old_backups(backup_dir)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
