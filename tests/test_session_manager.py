"""Tests for skillos.kernel.session_manager - Session CRUD, State Transitions, Limits"""

import time

from skillos.kernel.session_manager import SessionManager
from skillos._types import Session, SessionStatus


class TestCreateSession:
    def test_create_returns_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        assert isinstance(session, Session)

    def test_create_sets_user_id(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        assert session.user_id == "user-001"

    def test_create_sets_status_active(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        assert session.status == SessionStatus.ACTIVE

    def test_create_sets_metadata(self):
        sm = SessionManager()
        session = sm.create_session("user-001", metadata={"key": "val"})
        assert session.metadata == {"key": "val"}

    def test_create_with_empty_metadata(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        assert session.metadata == {}

    def test_create_generates_session_id(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        assert session.session_id is not None
        assert len(session.session_id) > 0

    def test_create_multiple_sessions_unique_ids(self):
        sm = SessionManager()
        s1 = sm.create_session("user-001")
        s2 = sm.create_session("user-001")
        assert s1.session_id != s2.session_id

    def test_create_multiple_users(self):
        sm = SessionManager()
        s1 = sm.create_session("user-a")
        s2 = sm.create_session("user-b")
        assert s1.user_id == "user-a"
        assert s2.user_id == "user-b"


class TestGetSession:
    def test_get_existing_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        retrieved = sm.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_nonexistent_session(self):
        sm = SessionManager()
        result = sm.get_session("nonexistent-id")
        assert result is None

    def test_get_returns_same_object(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        retrieved = sm.get_session(session.session_id)
        assert retrieved is session


class TestListSessions:
    def test_list_all_sessions(self):
        sm = SessionManager()
        sm.create_session("user-a")
        sm.create_session("user-b")
        sessions = sm.list_sessions()
        assert len(sessions) == 2

    def test_list_by_user(self):
        sm = SessionManager()
        sm.create_session("user-a")
        sm.create_session("user-a")
        sm.create_session("user-b")
        sessions = sm.list_sessions(user_id="user-a")
        assert len(sessions) == 2

    def test_list_by_status(self):
        sm = SessionManager()
        s1 = sm.create_session("user-a")
        s2 = sm.create_session("user-a")
        sm.complete_session(s1.session_id)
        sessions = sm.list_sessions(status=SessionStatus.ACTIVE)
        assert len(sessions) == 1
        assert sessions[0].session_id == s2.session_id

    def test_list_by_user_and_status(self):
        sm = SessionManager()
        s1 = sm.create_session("user-a")
        sm.create_session("user-a")
        sm.pause_session(s1.session_id)
        sessions = sm.list_sessions(user_id="user-a", status=SessionStatus.PAUSED)
        assert len(sessions) == 1
        assert sessions[0].session_id == s1.session_id

    def test_list_empty(self):
        sm = SessionManager()
        assert sm.list_sessions() == []

    def test_list_sorted_by_updated_at_desc(self):
        sm = SessionManager()
        s1 = sm.create_session("user-a")
        time.sleep(0.01)
        s2 = sm.create_session("user-a")
        sessions = sm.list_sessions()
        assert sessions[0].session_id == s2.session_id
        assert sessions[1].session_id == s1.session_id


class TestAddItem:
    def test_add_item_to_active_session(self, active_session):
        sm = SessionManager()
        sm._sessions[active_session.session_id] = active_session
        result = sm.add_item(active_session.session_id, {"data": "test"})
        assert result is True
        assert len(active_session.items) == 1

    def test_add_item_updates_timestamp(self, active_session):
        sm = SessionManager()
        sm._sessions[active_session.session_id] = active_session
        old_time = active_session.updated_at
        time.sleep(0.01)
        sm.add_item(active_session.session_id, {"data": "test"})
        assert active_session.updated_at > old_time

    def test_add_item_nonexistent_session(self):
        sm = SessionManager()
        result = sm.add_item("nonexistent", {"data": "test"})
        assert result is False

    def test_add_item_to_paused_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.pause_session(session.session_id)
        result = sm.add_item(session.session_id, {"data": "test"})
        assert result is False
        assert len(session.items) == 0

    def test_add_item_to_completed_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        result = sm.add_item(session.session_id, {"data": "test"})
        assert result is False

    def test_add_multiple_items(self, active_session):
        sm = SessionManager()
        sm._sessions[active_session.session_id] = active_session
        sm.add_item(active_session.session_id, {"i": 1})
        sm.add_item(active_session.session_id, {"i": 2})
        sm.add_item(active_session.session_id, {"i": 3})
        assert len(active_session.items) == 3


class TestAddAsset:
    def test_add_asset(self, active_session):
        sm = SessionManager()
        sm._sessions[active_session.session_id] = active_session
        result = sm.add_asset(active_session.session_id, "asset-001")
        assert result is True
        assert "asset-001" in active_session.assets

    def test_add_duplicate_asset(self, active_session):
        sm = SessionManager()
        sm._sessions[active_session.session_id] = active_session
        sm.add_asset(active_session.session_id, "asset-001")
        result = sm.add_asset(active_session.session_id, "asset-001")
        assert result is True
        assert len(active_session.assets) == 1

    def test_add_asset_nonexistent_session(self):
        sm = SessionManager()
        result = sm.add_asset("nonexistent", "asset-001")
        assert result is False

    def test_add_asset_updates_timestamp(self, active_session):
        sm = SessionManager()
        sm._sessions[active_session.session_id] = active_session
        old_time = active_session.updated_at
        time.sleep(0.01)
        sm.add_asset(active_session.session_id, "asset-001")
        assert active_session.updated_at > old_time


class TestPauseSession:
    def test_pause_active_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        result = sm.pause_session(session.session_id)
        assert result is True
        assert session.status == SessionStatus.PAUSED

    def test_pause_nonexistent_session(self):
        sm = SessionManager()
        result = sm.pause_session("nonexistent")
        assert result is False

    def test_pause_already_paused_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.pause_session(session.session_id)
        result = sm.pause_session(session.session_id)
        assert result is False

    def test_pause_completed_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        result = sm.pause_session(session.session_id)
        assert result is False


class TestResumeSession:
    def test_resume_paused_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.pause_session(session.session_id)
        result = sm.resume_session(session.session_id)
        assert result is True
        assert session.status == SessionStatus.ACTIVE

    def test_resume_nonexistent_session(self):
        sm = SessionManager()
        result = sm.resume_session("nonexistent")
        assert result is False

    def test_resume_active_session_fails(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        result = sm.resume_session(session.session_id)
        assert result is False

    def test_resume_completed_session_fails(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        result = sm.resume_session(session.session_id)
        assert result is False


class TestCompleteSession:
    def test_complete_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        result = sm.complete_session(session.session_id)
        assert result is True
        assert session.status == SessionStatus.COMPLETED

    def test_complete_nonexistent_session(self):
        sm = SessionManager()
        result = sm.complete_session("nonexistent")
        assert result is False

    def test_complete_already_completed(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        result = sm.complete_session(session.session_id)
        assert result is True


class TestAbortSession:
    def test_abort_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        result = sm.abort_session(session.session_id)
        assert result is True
        assert session.status == SessionStatus.ABORTED

    def test_abort_nonexistent_session(self):
        sm = SessionManager()
        result = sm.abort_session("nonexistent")
        assert result is False


class TestSessionLimits:
    def test_max_sessions_per_user(self):
        sm = SessionManager(max_sessions=2)
        sm.create_session("user-001")
        sm.create_session("user-001")
        sm.complete_session(sm.list_sessions("user-001")[0].session_id)
        sm.create_session("user-001")
        user_sessions = sm._user_sessions.get("user-001", [])
        assert len(user_sessions) <= 2

    def test_max_items_per_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        max_items = 1000
        for i in range(max_items):
            sm.add_item(session.session_id, {"i": i})
        result = sm.add_item(session.session_id, {"overflow": True})
        assert result is False
        assert len(session.items) == max_items

    def test_custom_max_sessions(self):
        sm = SessionManager(max_sessions=5)
        assert sm._max_sessions == 5


class TestCleanupExpired:
    def test_cleanup_no_expired(self):
        sm = SessionManager()
        sm.create_session("user-001")
        count = sm.cleanup_expired(max_age_hours=24)
        assert count == 0

    def test_cleanup_completed_old_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        session.updated_at = time.time() - 25 * 3600
        count = sm.cleanup_expired(max_age_hours=24)
        assert count == 1
        assert sm.get_session(session.session_id) is None

    def test_cleanup_aborted_old_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.abort_session(session.session_id)
        session.updated_at = time.time() - 48 * 3600
        count = sm.cleanup_expired(max_age_hours=24)
        assert count == 1

    def test_cleanup_preserves_active_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        session.updated_at = time.time() - 100 * 3600
        count = sm.cleanup_expired(max_age_hours=24)
        assert count == 0
        assert sm.get_session(session.session_id) is not None

    def test_cleanup_preserves_paused_session(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.pause_session(session.session_id)
        session.updated_at = time.time() - 100 * 3600
        count = sm.cleanup_expired(max_age_hours=24)
        assert count == 0

    def test_cleanup_removes_user_session_ref(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        session.updated_at = time.time() - 25 * 3600
        sm.cleanup_expired(max_age_hours=24)
        user_sessions = sm._user_sessions.get("user-001", [])
        assert session.session_id not in user_sessions

    def test_cleanup_custom_max_age(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.complete_session(session.session_id)
        session.updated_at = time.time() - 2 * 3600
        count = sm.cleanup_expired(max_age_hours=1)
        assert count == 1


class TestSearchSessions:
    def test_search_by_metadata_value(self):
        sm = SessionManager()
        s1 = sm.create_session("user-001", metadata={"project": "alpha"})
        sm.create_session("user-001", metadata={"project": "beta"})
        results = sm.search_sessions("user-001", "alpha")
        assert len(results) == 1
        assert results[0].session_id == s1.session_id

    def test_search_case_insensitive(self):
        sm = SessionManager()
        sm.create_session("user-001", metadata={"project": "Alpha"})
        results = sm.search_sessions("user-001", "alpha")
        assert len(results) == 1

    def test_search_no_match(self):
        sm = SessionManager()
        sm.create_session("user-001", metadata={"project": "alpha"})
        results = sm.search_sessions("user-001", "nonexistent")
        assert len(results) == 0

    def test_search_only_active_sessions(self):
        sm = SessionManager()
        s1 = sm.create_session("user-001", metadata={"project": "alpha"})
        s2 = sm.create_session("user-001", metadata={"project": "alpha"})
        sm.pause_session(s2.session_id)
        results = sm.search_sessions("user-001", "alpha")
        assert len(results) == 1
        assert results[0].session_id == s1.session_id


class TestSessionStats:
    def test_stats_empty(self):
        sm = SessionManager()
        stats = sm.get_session_stats()
        assert stats["total_sessions"] == 0

    def test_stats_single_session(self):
        sm = SessionManager()
        sm.create_session("user-001")
        stats = sm.get_session_stats()
        assert stats["total_sessions"] == 1
        assert stats["by_status"]["active"] == 1

    def test_stats_with_items_and_assets(self):
        sm = SessionManager()
        session = sm.create_session("user-001")
        sm.add_item(session.session_id, {"data": 1})
        sm.add_item(session.session_id, {"data": 2})
        sm.add_asset(session.session_id, "asset-001")
        stats = sm.get_session_stats()
        assert stats["total_items"] == 2
        assert stats["total_assets"] == 1
        assert stats["avg_items_per_session"] == 2.0

    def test_stats_by_user(self):
        sm = SessionManager()
        sm.create_session("user-a")
        sm.create_session("user-a")
        sm.create_session("user-b")
        stats = sm.get_session_stats(user_id="user-a")
        assert stats["total_sessions"] == 2

    def test_stats_by_status_breakdown(self):
        sm = SessionManager()
        s1 = sm.create_session("user-001")
        sm.create_session("user-001")
        sm.pause_session(s1.session_id)
        stats = sm.get_session_stats()
        assert stats["by_status"]["active"] == 1
        assert stats["by_status"]["paused"] == 1
