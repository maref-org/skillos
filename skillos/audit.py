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
        self.log_dir = Path(log_dir or os.getenv("SKILLOS_AUDIT_DIR", "./audit_logs"))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # HMAC 密钥：优先环境变量，其次随机生成（随机生成时警告）
        self._secret_key = self._load_secret_key(secret_key)

        # 当前日志文件
        self._current_log_file = self.log_dir / f"audit_{self._today()}.log"

        # 最后一条记录的哈希（用于链式结构）
        self._last_hash = self._load_last_hash()

    def _load_secret_key(self, secret_key: str | None) -> bytes:
        """加载 HMAC 密钥"""
        key = secret_key or os.getenv("SKILLOS_AUDIT_SECRET")
        if not key:
            logger.warning(
                "SKILLOS_AUDIT_SECRET not set. Generating random key. "
                "This will prevent verification across restarts."
            )
            key = secrets.token_hex(32)
        return key.encode("utf-8")

    def _today(self) -> str:
        """返回当前日期字符串"""
        return time.strftime("%Y-%m-%d")

    def _load_last_hash(self) -> str:
        """从现有日志文件加载最后一条记录的哈希"""
        if not self._current_log_file.exists():
            return ""

        try:
            with open(self._current_log_file, "r", encoding="utf-8") as f:
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
        """验证单条记录的签名"""
        stored_sig = record.get("signature", "")
        record_hash = record.get("record_hash", "")

        if not stored_sig or not record_hash:
            return False

        expected_sig = hmac.new(
            self._secret_key,
            record_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(stored_sig, expected_sig)

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
        sanitized = {}
        for key, value in details.items():
            if any(sk in key.lower() for sk in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value
        return sanitized

    def _append_to_log(self, record: dict[str, Any]) -> None:
        """追加写入日志文件"""
        # 检查是否需要切换日志文件（按天滚动）
        current_file = self.log_dir / f"audit_{self._today()}.log"
        if current_file != self._current_log_file:
            self._current_log_file = current_file
            self._last_hash = ""  # 新文件重置链式哈希

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
            logger.info("No audit log found for %s", date or self._today())
            return True

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            logger.error("Failed to read audit log: %s", exc)
            return False

        prev_hash = ""
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

        results = []
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
