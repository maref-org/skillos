#!/usr/bin/env python3
"""Audit Logger — 防篡改审计日志系统

职责：
  - 记录所有敏感操作（身份验证、Skill 执行、结算、状态变更）
  - Append-only 存储，每条记录 HMAC-SHA256 签名
  - 支持链式校验（每条记录包含前一条记录的哈希）
  - 结构化 JSON 输出，对接 ELK/Loki

安全特性：
  - 日志一旦写入不可修改（append-only）
  - HMAC 签名防止篡改
  - 链式哈希检测删除/插入
  - 敏感字段脱敏
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditEventType(StrEnum):
    """审计事件类型"""

    IDENTITY_REGISTERED = "identity.registered"
    IDENTITY_VERIFIED = "identity.verified"
    IDENTITY_SIGN = "identity.sign"
    SKILL_REGISTERED = "skill.registered"
    SKILL_PUBLISHED = "skill.published"
    SKILL_EXECUTED = "skill.executed"
    SKILL_DEPRECATED = "skill.deprecated"
    SESSION_CREATED = "session.created"
    SESSION_COMPLETED = "session.completed"
    SETTLEMENT_SUBMITTED = "settlement.submitted"
    SETTLEMENT_AUTO = "settlement.auto"
    SETTLEMENT_TRIGGERED = "settlement.triggered"
    CONFIG_CHANGED = "config.changed"
    AUTH_FAILURE = "auth.failure"
    AUTH_SUCCESS = "auth.success"
    SYSTEM_ERROR = "system.error"


@dataclass
class AuditRecord:
    """审计记录"""

    event_type: AuditEventType
    actor_id: str  # 操作者身份标识
    resource_id: str  # 被操作资源标识
    action: str  # 操作描述
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    record_id: str = field(default_factory=lambda: secrets.token_hex(16))
    prev_hash: str = ""  # 前一条记录的哈希（链式结构）
    signature: str = ""  # HMAC 签名


class AuditLogger:
    """防篡改审计日志器

    使用方式：
        audit = AuditLogger()
        audit.log(AuditEventType.SKILL_EXECUTED, "user_123", "skill_456",
                  "Execute skill", {"input": "...", "output": "..."})

        # 验证日志完整性
        is_valid = audit.verify_chain()
    """

    def __init__(
        self,
        log_dir: str | None = None,
        secret_key: str | None = None,
    ):
        self.log_dir = Path(str(log_dir or os.getenv("SKILLOS_AUDIT_DIR", "./audit_logs")))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # HMAC 密钥：优先环境变量；否则使用审计目录内持久化密钥文件，
        # 保证进程重启后既有链仍可验签（文件权限 0600）。
        self._secret_key = self._load_secret_key(secret_key)

        # 当前日志文件
        self._current_log_file = self.log_dir / f"audit_{self._today()}.log"

        # 最后一条记录的哈希（用于链式结构）
        self._last_hash = self._load_last_hash()

        # C10：实例级写锁——log() 的「读 prev_hash → 计算 → 写回」必须串行化，
        # 否则并发线程读到同一 _last_hash 会产生两条同 prev_hash 记录（断链）
        self._write_lock = threading.Lock()

    SECRET_FILENAME = ".audit_secret"

    def _load_secret_key(self, secret_key: str | None) -> bytes:
        """加载 HMAC 密钥（env > 持久化密钥文件 > 新建 0600 密钥文件）。"""
        key = secret_key or os.getenv("SKILLOS_AUDIT_SECRET")
        if key:
            return key.encode("utf-8")

        secret_path = self.log_dir / self.SECRET_FILENAME
        if secret_path.exists():
            return secret_path.read_text(encoding="utf-8").strip().encode("utf-8")

        generated = secrets.token_hex(32)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(secret_path, flags, 0o600)
        try:
            os.write(fd, generated.encode("utf-8"))
        finally:
            os.close(fd)
        try:
            os.chmod(secret_path, 0o600)
        except OSError:
            pass
        logger.warning(
            "SKILLOS_AUDIT_SECRET not set; generated persistent key at %s (mode 0600). "
            "Set the env var in production to share the key across hosts.",
            secret_path,
        )
        return generated.encode("utf-8")

    def _today(self) -> str:
        """返回当前日期字符串"""
        return time.strftime("%Y-%m-%d")

    def _load_last_hash(self) -> str:
        """从现有日志文件加载最后一条记录的哈希。

        C10 修复：当日文件不存在时（如跨天重启），回退到最近的历史审计文件，
        保证新文件首条记录仍锚定历史链尾，不重置为空。
        """
        candidates = [self._current_log_file]
        if not self._current_log_file.exists():
            # 当日文件不存在 → 找目录下日期最大的历史文件
            existing = sorted(self.log_dir.glob("audit_*.log"), reverse=True)
            candidates = existing or candidates

        for path in candidates:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_record = json.loads(lines[-1])
                        return last_record.get("record_hash", "")
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load last hash from audit log: %s", exc)

        return ""

    def _prev_day_last_hash(self, log_file: Path) -> str:
        """返回目标日期**之前**最近日志文件的末条 record_hash（跨天锚定起点）。

        C10 修复：新一天首条记录的 prev_hash 指向上一日末条 hash，
        verify_chain 必须用同一锚定起点，否则多日日志恒报断链。
        从 `log_file` 的日期向前回溯，取日期小于目标日期的最大文件。
        """
        target_name = log_file.name
        candidates = [
            path for path in sorted(self.log_dir.glob("audit_*.log"), reverse=True) if path.name < target_name
        ]
        for path in candidates:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if lines:
                        last_record = json.loads(lines[-1])
                        return last_record.get("record_hash", "")
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load last hash from audit log: %s", exc)
        return ""

    def _compute_record_hash(self, record: AuditRecord) -> str:
        """计算记录的内容哈希（不含 signature 字段）"""
        data = {
            "event_type": record.event_type.value,
            "actor_id": record.actor_id,
            "resource_id": record.resource_id,
            "action": record.action,
            "details": record.details,
            "timestamp": record.timestamp,
            "record_id": record.record_id,
            "prev_hash": record.prev_hash,
        }
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _sign_record(self, record_hash: str) -> str:
        """使用 HMAC-SHA256 签名记录哈希"""
        return hmac.new(
            self._secret_key,
            record_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_record_signature(self, record: dict[str, Any]) -> bool:
        """验证单条记录的签名（HMAC + 内容哈希一致性）。

        C10 修复：除 HMAC 签名外，重算内容哈希并与存储的 record_hash 比对，
        防止攻击者篡改内容后保留原 record_hash+signature 蒙混。
        """
        stored_sig = record.get("signature", "")
        stored_hash = record.get("record_hash", "")

        if not stored_sig or not stored_hash:
            return False

        expected_sig = hmac.new(
            self._secret_key,
            stored_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(stored_sig, expected_sig):
            return False

        # 重算内容哈希：篡改任何字段（actor/resource/action/details/timestamp 等）
        # 都会使 record_hash 与内容不匹配
        recomputed = self._compute_record_hash_from_dict(record)
        return hmac.compare_digest(recomputed, stored_hash)

    def _compute_record_hash_from_dict(self, record: dict[str, Any]) -> str:
        """从存储的 dict 重建内容哈希（与 _compute_record_hash 一致）。"""
        data = {
            "event_type": record.get("event_type", ""),
            "actor_id": record.get("actor_id", ""),
            "resource_id": record.get("resource_id", ""),
            "action": record.get("action", ""),
            "details": record.get("details", {}),
            "timestamp": record.get("timestamp", 0),
            "record_id": record.get("record_id", ""),
            "prev_hash": record.get("prev_hash", ""),
        }
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def log(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """记录审计事件

        Args:
            event_type: 事件类型
            actor_id: 操作者身份标识
            resource_id: 被操作资源标识
            action: 操作描述
            details: 附加详情（敏感字段会被脱敏）

        Returns:
            AuditRecord: 生成的审计记录
        """
        # C10：整段「读 prev_hash → 计算 → 追加 → 更新 _last_hash」加锁串行化，
        # 避免并发写产生同 prev_hash 记录破坏链
        with self._write_lock:
            return self._log_locked(event_type, actor_id, resource_id, action, details)

    def _log_locked(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """加锁版本 log()——调用方须持有 self._write_lock。"""
        # 脱敏处理
        safe_details = self._sanitize_details(details or {})

        record = AuditRecord(
            event_type=event_type,
            actor_id=actor_id,
            resource_id=resource_id,
            action=action,
            details=safe_details,
            prev_hash=self._last_hash,
        )

        # 计算哈希并签名
        record_hash = self._compute_record_hash(record)
        record.signature = self._sign_record(record_hash)

        # 构建完整记录（含 record_hash）
        full_record = {
            **asdict(record),
            "event_type": record.event_type.value,
            "record_hash": record_hash,
        }

        # 写入日志文件（append-only）
        self._append_to_log(full_record)

        # 更新链式哈希
        self._last_hash = record_hash

        logger.debug(
            "Audit logged: %s by %s on %s",
            event_type.value,
            actor_id,
            resource_id,
        )

        return record

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """脱敏处理敏感字段"""
        sensitive_keys = {
            "password",
            "secret",
            "token",
            "api_key",
            "private_key",
            "credit_card",
            "ssn",
        }
        sanitized: dict[str, Any] = {}
        for key, value in details.items():
            if any(sk in key.lower() for sk in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value
        return sanitized

    def _append_to_log(self, record: dict[str, Any]) -> None:
        """追加写入日志文件（调用方须持有 self._write_lock）"""
        # 检查是否需要切换日志文件（按天滚动）
        current_file = self.log_dir / f"audit_{self._today()}.log"
        if current_file != self._current_log_file:
            self._current_log_file = current_file
            # C10：跨天不重置链——新文件首条记录锚定上一日文件最后 hash，
            # 保持全链连续，防止跨天断链/静默插删
            self._last_hash = self._load_last_hash()

        try:
            with open(self._current_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.error("Failed to write audit log: %s", exc)
            raise

    def verify_chain(self, date: str | None = None) -> bool:
        """验证审计日志链的完整性

        检查：
        1. 每条记录的签名是否有效
        2. 每条记录的 prev_hash 是否与前一条记录的 record_hash 匹配
        3. 是否有记录被篡改或删除

        Args:
            date: 指定日期（格式：YYYY-MM-DD），None 表示今天

        Returns:
            bool: 链是否完整
        """
        log_file = self.log_dir / f"audit_{date or self._today()}.log"
        if not log_file.exists():
            # C10：缺失日志文件应视为可疑（可静默删日志）。
            # 但整个目录从未写过日志时（冷启动未审计）不算异常。
            if not any(self.log_dir.glob("audit_*.log")):
                logger.info("No audit logs exist yet — nothing to verify")
                return True
            logger.warning("Audit log file missing (possible tampering): %s", log_file)
            return False

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            logger.error("Failed to read audit log: %s", exc)
            return False

        # C10：跨天锚定——目标日期首条记录的 prev_hash 指向上一日末条 record_hash。
        # 若前一日存在日志，则起始 prev_hash 应为上一日末条 hash（而非空串）。
        prev_hash = self._prev_day_last_hash(log_file)
        for i, line in enumerate(lines):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON at line %d: %s", i + 1, exc)
                return False

            # 验证签名
            if not self._verify_record_signature(record):
                logger.error("Signature verification failed at line %d", i + 1)
                return False

            # 验证链式哈希
            if record.get("prev_hash") != prev_hash:
                logger.error(
                    "Chain broken at line %d: expected prev_hash=%s, got=%s",
                    i + 1,
                    prev_hash,
                    record.get("prev_hash"),
                )
                return False

            prev_hash = record.get("record_hash", "")

        logger.info("Audit chain verified: %d records, intact", len(lines))
        return True

    def query(
        self,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        resource_id: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询审计日志

        Args:
            event_type: 按事件类型过滤
            actor_id: 按操作者过滤
            resource_id: 按资源过滤
            start_time: 开始时间戳
            end_time: 结束时间戳
            date: 指定日期（YYYY-MM-DD）
            limit: 最大返回条数

        Returns:
            list[dict]: 匹配的审计记录
        """
        log_file = self.log_dir / f"audit_{date or self._today()}.log"
        if not log_file.exists():
            return []

        results: list[dict] = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if len(results) >= limit:
                        break

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event_type and record.get("event_type") != event_type.value:
                        continue
                    if actor_id and record.get("actor_id") != actor_id:
                        continue
                    if resource_id and record.get("resource_id") != resource_id:
                        continue
                    if start_time and record.get("timestamp", 0) < start_time:
                        continue
                    if end_time and record.get("timestamp", 0) > end_time:
                        continue

                    results.append(record)
        except OSError as exc:
            logger.error("Failed to query audit log: %s", exc)

        return results

    def export(self, date: str | None = None) -> str:
        """导出指定日期的审计日志为 JSON 字符串

        Args:
            date: 指定日期（YYYY-MM-DD），None 表示今天

        Returns:
            str: JSON 格式的审计日志
        """
        log_file = self.log_dir / f"audit_{date or self._today()}.log"
        if not log_file.exists():
            return "[]"

        records = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:
            logger.error("Failed to export audit log: %s", exc)

        return json.dumps(records, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------
# Module-level singleton + convenience function
# ----------------------------------------------------------------------
#
# 设计意图：
#   - 业务代码零样板：`from skillos.audit import log_audit, AuditEventType`
#     然后 `log_audit(AuditEventType.SKILL_EXECUTED, actor, res, action, details)`
#   - 单例避免每次创建 AuditLogger 重复加载链式哈希
#   - log_audit 全 try/except 包裹，审计失败绝不阻塞主业务流程
#   - 测试隔离：通过 SKILLOS_AUDIT_DIR 环境变量指向 tmp_path，或
#     set _default_logger = None 强制重新初始化
# ----------------------------------------------------------------------

_default_logger: AuditLogger | None = None
_default_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """返回进程级 AuditLogger 单例（lazy init）。

    单例初始化失败时（如审计目录不可写）抛出异常；调用方应优先使用
    `log_audit()` 便捷函数，它会捕获所有异常。
    """
    global _default_logger
    if _default_logger is None:
        with _default_lock:
            if _default_logger is None:
                _default_logger = AuditLogger()
    return _default_logger


def reset_audit_logger() -> None:
    """重置单例（仅供测试使用）。

    下次调用 get_audit_logger() 时会重新初始化，读取最新的
    SKILLOS_AUDIT_DIR / SKILLOS_AUDIT_SECRET 环境变量。
    """
    global _default_logger
    with _default_lock:
        _default_logger = None


def log_audit(
    event_type: AuditEventType,
    actor_id: str,
    resource_id: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """便捷审计函数 — 业务路径统一入口。

    特性：
      - 模块级单例，避免重复初始化开销
      - 全 try/except 包裹，审计失败仅 logger.error，不抛异常
      - 敏感字段自动脱敏（password/secret/token/api_key 等）

    Args:
        event_type: AuditEventType 枚举值
        actor_id: 操作者身份标识（无 user context 时用 "system"）
        resource_id: 被操作资源标识
        action: 操作描述
        details: 附加详情（可选，敏感字段自动脱敏）
    """
    try:
        audit = get_audit_logger()
        audit.log(event_type, actor_id, resource_id, action, details)
    except Exception as exc:  # noqa: BLE001 — 审计绝不阻塞主业务
        logger.error(
            "Audit log failed (event=%s actor=%s resource=%s): %s",
            event_type.value,
            actor_id,
            resource_id,
            exc,
        )
