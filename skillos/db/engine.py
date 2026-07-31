#!/usr/bin/env python3
"""skillos.db.engine — 数据库引擎与会话管理

支持 SQLite（开发/测试）和 PostgreSQL（生产）。
通过环境变量 SKILLOS_DATABASE_URL 配置连接字符串。
"""

import logging
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from skillos.db.models import Base

logger = logging.getLogger(__name__)

_DEFAULT_SQLITE_URL = "sqlite:///./skillos.db"

_engine = None
_SessionLocal = None


def get_database_url() -> str:
    """获取数据库连接字符串。

    优先级：
    1. 环境变量 SKILLOS_DATABASE_URL
    2. 默认 SQLite（本地文件）
    """
    return os.getenv("SKILLOS_DATABASE_URL", _DEFAULT_SQLITE_URL)


def get_engine():
    """获取或创建 SQLAlchemy 引擎（单例）。"""
    global _engine
    if _engine is None:
        url = get_database_url()
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        # 内存 SQLite 需 StaticPool：否则每个连接独立数据库，跨请求/连接丢失表
        if url in ("sqlite://", "sqlite:///:memory:"):
            _engine = create_engine(
                url,
                echo=os.getenv("SKILLOS_DB_ECHO", "0") == "1",
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            _engine = create_engine(
                url,
                echo=os.getenv("SKILLOS_DB_ECHO", "0") == "1",
                connect_args=connect_args,
                pool_pre_ping=True,
            )
        logger.info("Database engine created: %s", url.split("://")[0])
        Base.metadata.create_all(bind=_engine)
    return _engine


def get_sessionmaker():
    """获取会话工厂（单例）。"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """生成器方式获取数据库会话，用于依赖注入或 with 语句。"""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 全局 SessionLocal 实例，供需要直接创建会话的模块使用
SessionLocal = get_sessionmaker()


def init_db() -> None:
    """初始化数据库：创建所有表。"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized (tables created if not exist)")


def reset_db() -> None:
    """重置数据库：删除并重新创建所有表（仅用于测试）。"""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.warning("Database reset (all tables dropped and recreated)")
