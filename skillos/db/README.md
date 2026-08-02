---
schema_version: "1.0"
type: source_module
purpose: "Database layer — SQLAlchemy models, engine, session management"
files:
  - "models.py: ORM models (AuditLogModel, etc.)"
  - "engine.py: DB engine factory, get_engine(), SessionLocal"
  - "repository.py: Generic CRUD repository pattern"
freshness:
  updated: "2026-07-04"
  version: "0.5.0-beta"
entry_point: "engine.py"
agent_instruction: |
  SQLAlchemy database layer.
  - Engine lazy initialization via get_engine()
  - Session management via SessionLocal
  - Models for audit log persistence
  If a task involves "database" or "persistence", start in engine.py.
tags: [skillos, database, sqlalchemy, orm]
cross_reference:
  - "../kernel/ - 执行引擎（使用 DB 层）"
  - "../audit.py - 审计模块（写入 DB）"
  - "../observability/ - 可观测性（监控 DB 指标）"
---

# db/

SQLAlchemy database layer — models, engine, session management.
