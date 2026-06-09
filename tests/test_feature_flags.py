"""Tests for feature flag system (Phase 5.1).

覆盖场景：
  1. 布尔开关
  2. 百分比灰度
  3. 用户白名单
  4. 金丝雀发布
  5. 动态更新（无需重启）
  6. 缓存刷新
  7. 线程安全
"""

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from skillos.db.engine import Base
from skillos.feature_flags import (
    FeatureFlagManager,
    FlagState,
    FlagType,
    is_enabled,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:", echo=False, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)  # noqa: N806
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置 FeatureFlagManager 单例。"""
    FeatureFlagManager._instance = None
    yield
    FeatureFlagManager._instance = None


@pytest.fixture
def manager(db_session):
    """提供已初始化的 FeatureFlagManager（使用内存 DB）。"""
    # 由于 FeatureFlagManager 使用 SessionLocal，我们需要 patch
    from skillos.db import engine as db_engine_module

    original_session_local = db_engine_module.SessionLocal

    SessionLocal = sessionmaker(bind=db_session.bind, expire_on_commit=False)  # noqa: N806
    db_engine_module.SessionLocal = SessionLocal

    mgr = FeatureFlagManager(refresh_interval=3600.0)
    yield mgr

    db_engine_module.SessionLocal = original_session_local


# =============================================================================
# Boolean flag tests
# =============================================================================


class TestBooleanFlag:
    def test_disabled_returns_false(self, manager):
        manager.create_flag("new-ui", FlagType.BOOLEAN, FlagState.DISABLED)
        assert manager.is_enabled("new-ui") is False

    def test_enabled_returns_true(self, manager):
        manager.create_flag("new-ui", FlagType.BOOLEAN, FlagState.ENABLED)
        assert manager.is_enabled("new-ui") is True

    def test_rollout_boolean_value_true(self, manager):
        manager.create_flag("new-ui", FlagType.BOOLEAN, FlagState.ROLLOUT, value=True)
        assert manager.is_enabled("new-ui") is True

    def test_rollout_boolean_value_false(self, manager):
        manager.create_flag("new-ui", FlagType.BOOLEAN, FlagState.ROLLOUT, value=False)
        assert manager.is_enabled("new-ui") is False

    def test_missing_flag_returns_false(self, manager):
        assert manager.is_enabled("nonexistent") is False


# =============================================================================
# Percentage flag tests
# =============================================================================


class TestPercentageFlag:
    def test_zero_percent_no_users(self, manager):
        manager.create_flag("rollout", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=0)
        assert manager.is_enabled("rollout", user_id="user-001") is False

    def test_hundred_percent_all_users(self, manager):
        manager.create_flag("rollout", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=100)
        assert manager.is_enabled("rollout", user_id="user-001") is True

    def test_fifty_percent_distribution(self, manager):
        manager.create_flag("rollout", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=50)
        enabled_count = sum(1 for i in range(1000) if manager.is_enabled("rollout", user_id=f"user-{i}"))
        # 50% 灰度，1000 用户应该在 400-600 之间
        assert 400 <= enabled_count <= 600

    def test_percentage_requires_user_id(self, manager):
        manager.create_flag("rollout", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=50)
        assert manager.is_enabled("rollout") is False


# =============================================================================
# User list flag tests
# =============================================================================


class TestUserListFlag:
    def test_user_in_list(self, manager):
        manager.create_flag("beta-feature", FlagType.USER_LIST, FlagState.ROLLOUT, value=["alice", "bob"])
        assert manager.is_enabled("beta-feature", user_id="alice") is True
        assert manager.is_enabled("beta-feature", user_id="bob") is True

    def test_user_not_in_list(self, manager):
        manager.create_flag("beta-feature", FlagType.USER_LIST, FlagState.ROLLOUT, value=["alice"])
        assert manager.is_enabled("beta-feature", user_id="charlie") is False

    def test_user_list_requires_user_id(self, manager):
        manager.create_flag("beta-feature", FlagType.USER_LIST, FlagState.ROLLOUT, value=["alice"])
        assert manager.is_enabled("beta-feature") is False


# =============================================================================
# Canary flag tests
# =============================================================================


class TestCanaryFlag:
    def test_canary_distribution(self, manager):
        manager.create_flag("canary-v2", FlagType.CANARY, FlagState.ROLLOUT, value=10)
        enabled_count = sum(1 for i in range(1000) if manager.is_enabled("canary-v2", user_id=f"user-{i}"))
        # 10% 金丝雀，1000 用户应该在 50-150 之间
        assert 50 <= enabled_count <= 150

    def test_canary_same_user_consistent(self, manager):
        manager.create_flag("canary-v2", FlagType.CANARY, FlagState.ROLLOUT, value=50)
        results = [manager.is_enabled("canary-v2", user_id="alice") for _ in range(10)]
        assert all(r == results[0] for r in results)


# =============================================================================
# CRUD tests
# =============================================================================


class TestFlagCrud:
    def test_create_and_get(self, manager):
        flag = manager.create_flag("test-flag", FlagType.BOOLEAN, FlagState.ENABLED)
        assert flag.name == "test-flag"
        assert flag.state == FlagState.ENABLED

        retrieved = manager.get_flag("test-flag")
        assert retrieved is not None
        assert retrieved.name == "test-flag"

    def test_create_duplicate_raises(self, manager):
        manager.create_flag("test-flag", FlagType.BOOLEAN)
        with pytest.raises(ValueError, match="already exists"):
            manager.create_flag("test-flag", FlagType.BOOLEAN)

    def test_update_flag(self, manager):
        manager.create_flag("test-flag", FlagType.BOOLEAN, FlagState.DISABLED)
        updated = manager.update_flag("test-flag", state=FlagState.ENABLED)
        assert updated is not None
        assert updated.state == FlagState.ENABLED
        assert manager.is_enabled("test-flag") is True

    def test_update_flag_value(self, manager):
        manager.create_flag("pct-flag", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=10)
        updated = manager.update_flag("pct-flag", value=50)
        assert updated is not None
        assert updated.value == 50

    def test_delete_flag(self, manager):
        manager.create_flag("test-flag", FlagType.BOOLEAN)
        assert manager.delete_flag("test-flag") is True
        assert manager.get_flag("test-flag") is None
        assert manager.is_enabled("test-flag") is False

    def test_delete_nonexistent(self, manager):
        assert manager.delete_flag("nonexistent") is False

    def test_list_flags(self, manager):
        manager.create_flag("flag-a", FlagType.BOOLEAN)
        manager.create_flag("flag-b", FlagType.PERCENTAGE)
        flags = manager.list_flags()
        assert len(flags) == 2
        names = {f.name for f in flags}
        assert names == {"flag-a", "flag-b"}


# =============================================================================
# Dynamic update tests
# =============================================================================


class TestDynamicUpdate:
    def test_update_without_restart(self, manager):
        manager.create_flag("dynamic", FlagType.BOOLEAN, FlagState.DISABLED)
        assert manager.is_enabled("dynamic") is False

        manager.update_flag("dynamic", state=FlagState.ENABLED)
        assert manager.is_enabled("dynamic") is True

    def test_percentage_rollout_progression(self, manager):
        manager.create_flag("gradual", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=0)
        assert manager.is_enabled("gradual", user_id="user-001") is False

        manager.update_flag("gradual", value=100)
        assert manager.is_enabled("gradual", user_id="user-001") is True


# =============================================================================
# Convenience function tests
# =============================================================================


class TestConvenienceFunctions:
    def test_is_enabled_function(self, manager):
        manager.create_flag("conv-flag", FlagType.BOOLEAN, FlagState.ENABLED)
        assert is_enabled("conv-flag") is True


# =============================================================================
# Thread safety tests
# =============================================================================


class TestThreadSafety:
    def test_concurrent_reads(self, manager):
        manager.create_flag("concurrent", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=50)

        results = []
        errors = []

        def worker():
            try:
                for _ in range(100):
                    results.append(manager.is_enabled("concurrent", user_id="user-001"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 1000

    def test_concurrent_create(self, manager):
        errors = []
        created = []

        def worker(i):
            try:
                flag = manager.create_flag(f"flag-{i}", FlagType.BOOLEAN)
                created.append(flag)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(created) == 20
        assert len(manager.list_flags()) == 20


# =============================================================================
# Hash consistency tests
# =============================================================================


class TestHashConsistency:
    def test_same_user_same_result(self, manager):
        manager.create_flag("consistent", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=50)
        r1 = manager.is_enabled("consistent", user_id="alice")
        r2 = manager.is_enabled("consistent", user_id="alice")
        r3 = manager.is_enabled("consistent", user_id="alice")
        assert r1 == r2 == r3

    def test_different_users_different_results(self, manager):
        manager.create_flag("consistent", FlagType.PERCENTAGE, FlagState.ROLLOUT, value=50)
        results = {manager.is_enabled("consistent", user_id=f"user-{i}") for i in range(100)}
        # 应该同时有 True 和 False
        assert len(results) == 2
