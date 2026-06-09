"""skillos.feature_flags — 灰度发布与功能开关系统

Phase 5.1: 灰度发布机制

支持开关类型：
  - boolean: 布尔开关（开/关）
  - percentage: 百分比灰度（0-100）
  - user_list: 用户白名单
  - canary: 金丝雀发布（按用户 ID hash 百分比）

存储：DB 为唯一真相源，内存缓存加速读取。
更新：动态生效，无需重启。
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import skillos.db.engine as _db_engine
from skillos.db.models import FeatureFlagModel


class FlagType(str, Enum):
    """功能开关类型。"""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    CANARY = "canary"


class FlagState(str, Enum):
    """功能开关状态。"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    ROLLOUT = "rollout"  # 灰度中


@dataclass
class FeatureFlag:
    """功能开关值对象。"""

    name: str
    flag_type: FlagType
    state: FlagState
    value: Any = None  # percentage: int, user_list: list[str], boolean: bool
    description: str = ""
    updated_at: float = field(default_factory=time.time)


class FeatureFlagManager:
    """功能开关管理器。

    线程安全，支持动态更新，DB 为唯一真相源。
    """

    _instance: FeatureFlagManager | None = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> FeatureFlagManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, refresh_interval: float = 30.0) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._cache: dict[str, FeatureFlag] = {}
        self._cache_lock = threading.RLock()
        self._refresh_interval = refresh_interval
        self._last_refresh = 0.0
        self._load_from_db()

    # ------------------------------------------------------------------
    # Public API: 查询开关状态
    # ------------------------------------------------------------------

    def is_enabled(self, flag_name: str, user_id: str | None = None) -> bool:
        """判断功能开关是否对当前用户生效。

        Args:
            flag_name: 开关名称
            user_id: 用户 ID（percentage/canary 类型必需）
        """
        flag = self._get_flag(flag_name)
        if flag is None:
            return False

        if flag.state == FlagState.DISABLED:
            return False
        if flag.state == FlagState.ENABLED:
            return True

        # ROLLOUT 状态按类型判断
        if flag.flag_type == FlagType.BOOLEAN:
            return bool(flag.value)

        if flag.flag_type == FlagType.PERCENTAGE:
            if user_id is None:
                return False
            return self._hash_percentage(user_id, flag_name) < int(flag.value or 0)

        if flag.flag_type == FlagType.USER_LIST:
            if user_id is None:
                return False
            allowed = flag.value or []
            return user_id in allowed

        if flag.flag_type == FlagType.CANARY:
            if user_id is None:
                return False
            return self._hash_percentage(user_id, flag.name) < int(flag.value or 0)

        return False

    def get_flag(self, flag_name: str) -> FeatureFlag | None:
        """获取开关详情。"""
        return self._get_flag(flag_name)

    def list_flags(self) -> list[FeatureFlag]:
        """列出所有开关。"""
        self._maybe_refresh()
        with self._cache_lock:
            return list(self._cache.values())

    # ------------------------------------------------------------------
    # Public API: 管理开关
    # ------------------------------------------------------------------

    def create_flag(
        self,
        name: str,
        flag_type: FlagType,
        state: FlagState = FlagState.DISABLED,
        value: Any = None,
        description: str = "",
    ) -> FeatureFlag:
        """创建新开关。"""
        if not name or not isinstance(name, str):
            raise ValueError("flag name must be a non-empty string")

        session = _db_engine.SessionLocal()
        try:
            existing = session.query(FeatureFlagModel).filter_by(name=name).first()
            if existing is not None:
                raise ValueError(f"flag '{name}' already exists")

            model = FeatureFlagModel(
                name=name,
                flag_type=flag_type.value,
                state=state.value,
                value=value,
                description=description,
            )
            session.add(model)
            session.commit()

            flag = self._model_to_flag(model)
            with self._cache_lock:
                self._cache[name] = flag
            return flag
        finally:
            session.close()

    def update_flag(
        self,
        name: str,
        state: FlagState | None = None,
        value: Any = None,
        description: str | None = None,
    ) -> FeatureFlag | None:
        """更新开关状态（动态生效，无需重启）。"""
        session = _db_engine.SessionLocal()
        try:
            model = session.query(FeatureFlagModel).filter_by(name=name).first()
            if model is None:
                return None

            if state is not None:
                model.state = state.value
            if value is not None:
                model.value = value
            if description is not None:
                model.description = description

            session.commit()

            flag = self._model_to_flag(model)
            with self._cache_lock:
                self._cache[name] = flag
            return flag
        finally:
            session.close()

    def delete_flag(self, name: str) -> bool:
        """删除开关。"""
        session = _db_engine.SessionLocal()
        try:
            model = session.query(FeatureFlagModel).filter_by(name=name).first()
            if model is None:
                return False

            session.delete(model)
            session.commit()

            with self._cache_lock:
                self._cache.pop(name, None)
            return True
        finally:
            session.close()

    def refresh(self) -> None:
        """强制从 DB 刷新缓存。"""
        self._load_from_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_flag(self, name: str) -> FeatureFlag | None:
        self._maybe_refresh()
        with self._cache_lock:
            return self._cache.get(name)

    def _maybe_refresh(self) -> None:
        if time.time() - self._last_refresh > self._refresh_interval:
            self._load_from_db()

    def _load_from_db(self) -> None:
        session = _db_engine.SessionLocal()
        try:
            models = session.query(FeatureFlagModel).all()
            new_cache: dict[str, FeatureFlag] = {}
            for m in models:
                new_cache[m.name] = self._model_to_flag(m)
            with self._cache_lock:
                self._cache = new_cache
            self._last_refresh = time.time()
        finally:
            session.close()

    @staticmethod
    def _model_to_flag(model: FeatureFlagModel) -> FeatureFlag:
        return FeatureFlag(
            name=model.name,
            flag_type=FlagType(model.flag_type),
            state=FlagState(model.state),
            value=model.value,
            description=model.description or "",
            updated_at=model.updated_at.timestamp() if model.updated_at else time.time(),
        )

    @staticmethod
    def _hash_percentage(user_id: str, salt: str) -> int:
        """将 user_id 映射到 0-99 的百分比值（确定性 hash）。"""
        digest = hashlib.sha256(f"{user_id}:{salt}".encode()).hexdigest()
        return int(digest[:8], 16) % 100


# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------

_default_manager: FeatureFlagManager | None = None
_default_lock = threading.Lock()


def get_feature_flag_manager() -> FeatureFlagManager:
    global _default_manager
    if _default_manager is None:
        with _default_lock:
            if _default_manager is None:
                _default_manager = FeatureFlagManager()
    return _default_manager


def is_enabled(flag_name: str, user_id: str | None = None) -> bool:
    """便捷函数：判断开关是否生效。"""
    return get_feature_flag_manager().is_enabled(flag_name, user_id)
