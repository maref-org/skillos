"""审计链持久密钥：重启后仍可验签。"""

from __future__ import annotations

import os

from skillos.audit import AuditEventType, AuditLogger


def test_persisted_key_survives_restart(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLOS_AUDIT_SECRET", raising=False)
    log_dir = tmp_path / "audit_logs"

    first = AuditLogger(log_dir=str(log_dir))
    first.log(AuditEventType.SKILL_EXECUTED, "actor", "resource", "first")
    assert first.verify_chain() is True

    secret_file = log_dir / AuditLogger.SECRET_FILENAME
    assert secret_file.exists()
    assert oct(secret_file.stat().st_mode & 0o777) == oct(0o600)

    second = AuditLogger(log_dir=str(log_dir))
    second.log(AuditEventType.SKILL_EXECUTED, "actor", "resource", "second")
    assert second.verify_chain() is True


def test_env_secret_takes_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLOS_AUDIT_SECRET", "env-secret-value-1234567890")
    log_dir = tmp_path / "audit_logs"
    AuditLogger(log_dir=str(log_dir))
    assert not (log_dir / AuditLogger.SECRET_FILENAME).exists()


def test_tampered_record_fails_chain(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLOS_AUDIT_SECRET", raising=False)
    log_dir = tmp_path / "audit_logs"
    audit = AuditLogger(log_dir=str(log_dir))
    audit.log(AuditEventType.SKILL_EXECUTED, "actor", "resource", "ok")

    log_file = log_dir / f"audit_{audit._today()}.log"
    content = log_file.read_text(encoding="utf-8")
    log_file.write_text(content.replace('"ok"', '"tampered"'), encoding="utf-8")

    assert AuditLogger(log_dir=str(log_dir)).verify_chain() is False


def test_secret_file_is_not_world_readable(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLOS_AUDIT_SECRET", raising=False)
    log_dir = tmp_path / "audit_logs"
    AuditLogger(log_dir=str(log_dir))
    mode = os.stat(log_dir / AuditLogger.SECRET_FILENAME).st_mode
    assert mode & 0o077 == 0
