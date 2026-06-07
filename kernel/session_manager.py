#!/usr/bin/env python3
"""Session Manager — 会话生命周期管理

职责：
  - 会话创建、暂停、恢复、完成、终止
  - 会话内 Item 流式管理
  - 资产面板同步
  - 会话搜索与过滤
  - 内存使用监控
  - 跨会话状态持久化
"""

import logging
import time
from typing import Any

from skillos._types import Session, SessionStatus
from skillos.kernel.state_persistor import PersistentState, StatePersistor

logger = logging.getLogger(__name__)

_MAX_SESSIONS_PER_USER = 50
_MAX_ITEMS_PER_SESSION = 1000
_MAX_SESSION_AGE_HOURS = 24


class SessionManager:
    """会话管理器"""

    def __init__(self, max_sessions: int = _MAX_SESSIONS_PER_USER):
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[str, list[str]] = {}
        self._max_sessions = max_sessions
        self._state_store = StatePersistor()

    def create_session(self, user_id: str, metadata: dict[str, Any] | None = None) -> Session:
        """创建新会话"""
        if len(self._user_sessions.get(user_id, [])) >= self._max_sessions:
            self._cleanup_expired_sessions(user_id)

        session = Session(
            user_id=user_id,
            status=SessionStatus.ACTIVE,
            metadata=metadata or {},
        )

        self._sessions[session.session_id] = session
        self._user_sessions.setdefault(user_id, []).append(session.session_id)

        logger.info("Session created: %s for user %s", session.session_id, user_id)
        return session

    def get_session(self, session_id: str) -> Session | None:
        """获取会话"""
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        user_id: str | None = None,
        status: SessionStatus | None = None,
    ) -> list[Session]:
        """列出会话，可按用户和状态过滤"""
        sessions = list(self._sessions.values())

        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        if status:
            sessions = [s for s in sessions if s.status == status]

        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def add_item(self, session_id: str, item: dict[str, Any]) -> bool:
        """向会话添加 Item"""
        session = self._sessions.get(session_id)
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
        return True

    def add_asset(self, session_id: str, asset_id: str) -> bool:
        """向会话添加资产引用"""
        session = self._sessions.get(session_id)
        if session is None:
            return False

        if asset_id not in session.assets:
            session.assets.append(asset_id)
            session.updated_at = time.time()

        return True

    def pause_session(self, session_id: str) -> bool:
        """暂停会话"""
        session = self._sessions.get(session_id)
        if session is None or session.status != SessionStatus.ACTIVE:
            return False

        session.status = SessionStatus.PAUSED
        session.updated_at = time.time()
        logger.info("Session paused: %s", session_id)
        return True

    def resume_session(self, session_id: str) -> bool:
        """恢复会话"""
        session = self._sessions.get(session_id)
        if session is None or session.status != SessionStatus.PAUSED:
            return False

        session.status = SessionStatus.ACTIVE
        session.updated_at = time.time()
        logger.info("Session resumed: %s", session_id)
        return True

    def complete_session(self, session_id: str) -> bool:
        """完成会话"""
        session = self._sessions.get(session_id)
        if session is None:
            return False

        session.status = SessionStatus.COMPLETED
        session.updated_at = time.time()
        logger.info("Session completed: %s", session_id)
        return True

    def abort_session(self, session_id: str) -> bool:
        """终止会话"""
        session = self._sessions.get(session_id)
        if session is None:
            return False

        session.status = SessionStatus.ABORTED
        session.updated_at = time.time()
        logger.info("Session aborted: %s", session_id)
        return True

    def search_sessions(self, user_id: str, query: str) -> list[Session]:
        """搜索会话（基于 metadata）"""
        sessions = self.list_sessions(user_id=user_id, status=SessionStatus.ACTIVE)
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
        """清理过期会话"""
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        expired = []

        for sid, session in self._sessions.items():
            if (
                session.status in (SessionStatus.COMPLETED, SessionStatus.ABORTED)
                and (now - session.updated_at) > max_age_seconds
            ):
                expired.append(sid)

        for sid in expired:
            session = self._sessions.pop(sid, None)  # type: ignore[arg-type]
            if session:
                user_sessions = self._user_sessions.get(session.user_id, [])
                if sid in user_sessions:
                    user_sessions.remove(sid)

        logger.info("Cleaned up %d expired sessions", len(expired))
        return len(expired)

    def _cleanup_expired_sessions(self, user_id: str) -> None:
        user_sessions = self._user_sessions.get(user_id, [])
        expired = [
            sid for sid in user_sessions
            if (session := self._sessions.get(sid))
            and session.status in (SessionStatus.COMPLETED, SessionStatus.ABORTED)
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
            user_sessions.remove(sid)

    async def save_session_state(self, session_id: str, key: str, value: Any, ttl_seconds: int = 0) -> bool:
        """保存会话状态到持久化存储"""
        state = PersistentState(
            session_id=session_id,
            state_key=key,
            state_value=value,
            created_at="",
            updated_at="",
            ttl_seconds=ttl_seconds,
        )
        return self._state_store.save_state(state)

    async def load_session_state(self, session_id: str, key: str) -> Any | None:
        """从持久化存储加载会话状态"""
        return self._state_store.load_state(session_id, key)

    async def delete_session_state(self, session_id: str, key: str) -> bool:
        """从持久化存储删除会话状态"""
        return self._state_store.delete_state(session_id, key)

    async def list_session_states(self, session_id: str) -> list[dict]:
        """列出会话所有状态键"""
        return self._state_store.list_states(session_id)

    async def save_task_result(
        self,
        task_id: str,
        session_id: str,
        result: dict,
        context: dict,
        status: str = "completed",
    ) -> bool:
        """保存任务执行结果到 memory"""
        return self._state_store.save_task_result(task_id, session_id, result, context, status)

    async def get_task_history(self, session_id: str, limit: int = 10) -> list[dict]:
        """获取会话任务历史"""
        return self._state_store.get_task_history(session_id, limit)
