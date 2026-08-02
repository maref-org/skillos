"""skillos.version — 版本信息管理

Phase 5.2: 回滚机制支持
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 当前版本号（与 pyproject.toml 保持一致）
__version__ = "0.6.0-beta"

_DEFAULT_STATE_DIR = Path("./.skillos/state")


@dataclass
class DeploymentState:
    """部署状态快照。"""

    version: str
    deployed_at: str
    alembic_revision: str
    feature_flags: dict[str, Any]
    config_hash: str
    deployed_by: str = ""
    notes: str = ""


class VersionManager:
    """版本管理器：记录部署历史、支持一键回滚。"""

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self._state_dir = Path(state_dir) if state_dir else _DEFAULT_STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self._state_dir / "deployment_history.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_deployment(
        self,
        version: str,
        alembic_revision: str,
        feature_flags: dict[str, Any] | None = None,
        config_hash: str = "",
        deployed_by: str = "",
        notes: str = "",
    ) -> DeploymentState:
        """记录一次部署。"""
        state = DeploymentState(
            version=version,
            deployed_at=datetime.now(timezone.utc).isoformat(),
            alembic_revision=alembic_revision,
            feature_flags=feature_flags or {},
            config_hash=config_hash,
            deployed_by=deployed_by,
            notes=notes,
        )
        history = self._load_history()
        history.append(asdict(state))
        self._save_history(history)
        return state

    def get_history(self) -> list[DeploymentState]:
        """获取部署历史（从新到旧）。"""
        history = self._load_history()
        return [DeploymentState(**h) for h in reversed(history)]

    def get_current_version(self) -> str | None:
        """获取当前部署版本。"""
        history = self._load_history()
        if not history:
            return None
        return history[-1]["version"]

    def get_previous_revision(self) -> str | None:
        """获取上一个 Alembic revision（用于回滚）。"""
        history = self._load_history()
        if len(history) < 2:
            return None
        return history[-2]["alembic_revision"]

    def prepare_rollback(self) -> dict[str, Any] | None:
        """准备回滚信息。"""
        history = self._load_history()
        if len(history) < 2:
            return None

        current = history[-1]
        previous = history[-2]

        return {
            "from_version": current["version"],
            "to_version": previous["version"],
            "from_revision": current["alembic_revision"],
            "to_revision": previous["alembic_revision"],
            "feature_flags_to_restore": previous.get("feature_flags", {}),
        }

    def confirm_rollback(self, rollback_info: dict[str, Any]) -> bool:
        """确认回滚完成，更新历史记录。"""
        history = self._load_history()
        if not history:
            return False

        # 添加回滚记录
        rollback_state = DeploymentState(
            version=rollback_info["to_version"],
            deployed_at=datetime.now(timezone.utc).isoformat(),
            alembic_revision=rollback_info["to_revision"],
            feature_flags=rollback_info.get("feature_flags_to_restore", {}),
            config_hash="",
            deployed_by="rollback",
            notes=f"Rollback from {rollback_info['from_version']}",
        )
        history.append(asdict(rollback_state))
        self._save_history(history)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_history(self) -> list[dict[str, Any]]:
        if not self._history_file.exists():
            return []
        with open(self._history_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_history(self, history: list[dict[str, Any]]) -> None:
        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------

_default_manager: VersionManager | None = None


def get_version_manager() -> VersionManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = VersionManager()
    return _default_manager


def get_version() -> str:
    """获取当前版本号。"""
    return __version__
