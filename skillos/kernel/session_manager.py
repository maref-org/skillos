#!/usr/bin/env python3
"""Session Manager — 会话生命周期管理

职责：
  - 会话创建、暂停、恢复、完成、终止
  - 会话内 Item 流式管理
  - 资产面板同步
  - 会话搜索与过滤
  - 内存使用监控

数据持久化：
  - _sessions 保留为内存缓存，但 DB 为唯一真相源
  - 所有写操作同步到数据库
  - 读操作优先查缓存，miss 时查 DB 并回填
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

from skillos.db.engine import get_sessionmaker
from skillos.db.models import SessionModel
from skillos.db.repository import SessionRepository
from skillos.types import Session, SessionStatus

logger = logging.getLogger(__name__)

_MAX_SESSIONS_PER_USER = 50
_MAX_ITEMS_PER_SESSION = 1000
_MAX_SESSION_AGE_HOURS = 24


class SessionManager:
    """会话管理器"""

    def __init__(self, max_sessions: int = _MAX_SESSIONS_PER_USER, db_session: Any | None = None):
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, list[str]] = {}
        self._max_sessions = max_sessions
        self._db_session = db_session

    def _get_db(self):
        if self._db_session is not None:
            return self._db_session
        return get_sessionmaker()()

    @staticmethod
    def _model_to_session(model: SessionModel) -> Session:
        return Session(
            session_id=model.session_id,
            user_id=model.user_id,
            status=SessionStatus(model.status),
            items=model.items,
            assets=model.assets,
            created_at=model.created_at.timestamp(),
            updated_at=model.updated_at.timestamp(),
            metadata=model.metadata_json,
        )

    @staticmethod
    def _session_to_model(session: Session) -> SessionModel:
        return SessionModel(
            session_id=session.session_id,
            user_id=session.user_id,
            status=session.status.value,
            items=session.items,
            assets=session.assets,
            created_at=datetime.fromtimestamp(session.created_at, tz=timezone.utc),
            updated_at=datetime.fromtimestamp(session.updated_at, tz=timezone.utc),
            metadata_json=session.metadata,
        )

    def create_session(self, user_id: str, metadata: dict[str, Any] | None = None) -> Session:
        """创建新会话"""
        if len(self._user_sessions.get(user_id, [])) >= self._max_sessions:
            self._cleanup_expired_sessions(user_id)

        session = Session(
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            metadata=metadata or {},
        )

        # 持久化到 DB
        db = self._get_db()
        try:
            repo = SessionRepository(db)
            repo.save(self._session_to_model(session))
        finally:
            if self._db_session is None:
                db.close()

        self._sessions[session.session_id] = session
        self._user_sessions.setdefault(user_id, []).append(session.session_id)

        logger.info("Session created: %s for user %s", session.session_id, user_id)
        return session

    def get_session(self, session_id: str) -> Session | None:
        """获取会话（缓存优先，DB 回填）"""
        if session_id in self._sessions:
            return self._sessions[session_id]

        db = self._get_db()
        try:
            repo = SessionRepository(db)
            model = repo.get(session_id)
            if model is None:
                return None
            session = self._model_to_session(model)
            self._sessions[session_id] = session
            user_list = self._user_sessions.setdefault(session.user_id, [])
            if session_id not in user_list:
                user_list.append(session_id)
            return session
        finally:
            if self._db_session is None:
                db.close()

    def list_sessions(
        self,
        user_id: str | None = None,
        status: SessionStatus | None = None,
    ) -> list[Session]:
        """列出会话，可按用户和状态过滤（优先从 DB 加载）"""
        db = self._get_db()
        try:
            repo = SessionRepository(db)
            if user_id:
                models = repo.list_by_user(user_id, status=status.value if status else None)
            else:
                models = repo.list_all(status=status.value if status else None)
            sessions = [self._model_to_session(m) for m in models]
            # 同步刷新缓存
            for s in sessions:
                self._sessions[s.session_id] = s
                user_list = self._user_sessions.setdefault(s.user_id, [])
                if s.session_id not in user_list:
                    user_list.append(s.session_id)
            return sessions
        finally:
            if self._db_session is None:
                db.close()

    def add_item(self, session_id: str, item: dict[str, Any]) -> bool:
        """向会话添加 Item"""
        session = self.get_session(session_id)
        if session is None:
            return False

        if session.status != SessionStatus.ACTIVE:
            logger.warning("Cannot add item to %s session", session.status.value)
            return False

        if len(session.items) >= _MAX_ITEMS_PER_SESSION:
            logger.warning("Session %s reached max items limit", session_id)
            return False

        session.items.append(item)
        session.updated_at = time.time()

        # 同步到 DB
        db = self._get_db()
        try:
            repo = SessionRepository(db)
            repo.save(self._session_to_model(session))
        finally:
            if self._db_session is None:
                db.close()

        return True

    def add_asset(self, session_id: str, asset_id: str) -> bool:
        """向会话添加资产引用"""
        session = self.get_session(session_id)
        if session is None:
            return False

        if asset_id not in session.assets:
            session.assets.append(asset_id)
            session.updated_at = time.time()

            # 同步到 DB
            db = self._get_db()
            try:
                repo = SessionRepository(db)
                repo.save(self._session_to_model(session))
            finally:
                if self._db_session is None:
                    db.close()

        return True

    def pause_session(self, session_id: str) -> bool:
        """暂停会话"""
        session = self.get_session(session_id)
        if session is None or session.status != SessionStatus.ACTIVE:
            return False

        session.status = SessionStatus.PAUSED
        session.updated_at = time.time()

        db = self._get_db()
        try:
            repo = SessionRepository(db)
            repo.save(self._session_to_model(session))
        finally:
            if self._db_session is None:
                db.close()

        logger.info("Session paused: %s", session_id)
        return True

    def resume_session(self, session_id: str) -> bool:
        """恢复会话"""
        session = self.get_session(session_id)
        if session is None or session.status != SessionStatus.PAUSED:
            return False

        session.status = SessionStatus.ACTIVE
        session.updated_at = time.time()

        db = self._get_db()
        try:
            repo = SessionRepository(db)
            repo.save(self._session_to_model(session))
        finally:
            if self._db_session is None:
                db.close()

        logger.info("Session resumed: %s", session_id)
        return True

    def complete_session(self, session_id: str) -> bool:
        """完成会话"""
        session = self.get_session(session_id)
        if session is None:
            return False

        session.status = SessionStatus.COMPLETED
        session.updated_at = time.time()

        db = self._get_db()
        try:
            repo = SessionRepository(db)
            repo.save(self._session_to_model(session))
        finally:
            if self._db_session is None:
                db.close()

        logger.info("Session completed: %s", session_id)
        return True

    def abort_session(self, session_id: str) -> bool:
        """终止会话"""
        session = self.get_session(session_id)
        if session is None:
            return False

        session.status = SessionStatus.ABORTED
        session.updated_at = time.time()

        db = self._get_db()
        try:
            repo = SessionRepository(db)
            repo.save(self._session_to_model(session))
        finally:
            if self._db_session is None:
                db.close()

        logger.info("Session aborted: %s", session_id)
        return True

    def search_sessions(self, user_id: str, query: str) -> list[Session]:
        """搜索会话（基于 metadata）"""
        sessions = self.list_sessions(user_id=user_id)
        query_lower = query.lower()

        results = []
        for s in sessions:
            if query_lower in s.user_id.lower():
                results.append(s)
                continue
            for _k, v in s.metadata.items():
                if query_lower in str(v).lower():
                    results.append(s)
                    break

        return results

    def get_session_stats(self, user_id: str | None = None) -> dict[str, Any]:
        """获取会话统计"""
        sessions = self.list_sessions(user_id=user_id)

        by_status: dict[str, int] = {}
        total_items = 0
        total_assets = 0

        for s in sessions:
            by_status[s.status.value] = by_status.get(s.status.value, 0) + 1
            total_items += len(s.items)
            total_assets += len(s.assets)

        return {
            "total_sessions": len(sessions),
            "by_status": by_status,
            "total_items": total_items,
            "total_assets": total_assets,
            "avg_items_per_session": total_items / max(len(sessions), 1),
        }

    def cleanup_expired(self, max_age_hours: float = _MAX_SESSION_AGE_HOURS) -> int:
        """清理过期会话（DB + 缓存）"""
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        expired: list[str] = []

        for sid, session in self._sessions.items():
            if (
                session.status in (SessionStatus.COMPLETED, SessionStatus.ABORTED)
                and (now - session.updated_at) > max_age_seconds
            ):
                expired.append(sid)

        db = self._get_db()
        try:
            repo = SessionRepository(db)
            for sid in expired:
                session = self._sessions.pop(sid, None)  # type: ignore[arg-type]
                if session:
                    user_sessions = self._user_sessions.get(session.user_id, [])
                    if sid in user_sessions:
                        user_sessions.remove(sid)
                    repo.delete(sid)
        finally:
            if self._db_session is None:
                db.close()

        logger.info("Cleaned up %d expired sessions", len(expired))
        return len(expired)

    def _cleanup_expired_sessions(self, user_id: str) -> None:
        user_sessions = self._user_sessions.get(user_id, [])
        expired = [
            sid
            for sid in user_sessions
            if (session := self._sessions.get(sid))
            and session.status in (SessionStatus.COMPLETED, SessionStatus.ABORTED)
        ]
        db = self._get_db()
        try:
            repo = SessionRepository(db)
            for sid in expired:
                self._sessions.pop(sid, None)
                user_sessions.remove(sid)
                repo.delete(sid)
        finally:
            if self._db_session is None:
                db.close()
