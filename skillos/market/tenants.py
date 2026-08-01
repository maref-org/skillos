"""Tenant Service — 租户服务（L4 场景层）

垂直场景多租户上线的租户隔离单位：每个租户持有独立的 scene_config
（模板/档位/小费/角色集覆盖），契约通过 tenant_id 归入租户，
运营看板按租户聚合。scene_config 由 IpTrialScenario 读取以覆盖默认值。
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.models import TenantModel


class TenantService:
    """租户 CRUD + 场景配置管理。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def create(
        self,
        tenant_id: str,
        name: str = "",
        scene_config: dict[str, Any] | None = None,
    ) -> TenantModel:
        if self._db.query(TenantModel).filter(TenantModel.tenant_id == tenant_id).first() is not None:
            raise ValueError(f"Tenant already exists: {tenant_id}")
        now = datetime.now(timezone.utc)
        model = TenantModel(
            tenant_id=tenant_id,
            name=name,
            scene_config=scene_config or {},
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        self._db.flush()
        return model

    def get(self, tenant_id: str) -> TenantModel:
        model = self._db.query(TenantModel).filter(TenantModel.tenant_id == tenant_id).first()
        if model is None:
            raise ValueError(f"Tenant not found: {tenant_id}")
        return model

    def list(self) -> list[TenantModel]:
        return self._db.query(TenantModel).order_by(TenantModel.created_at.asc()).all()

    def update_scene_config(self, tenant_id: str, scene_config: dict[str, Any]) -> TenantModel:
        model = self.get(tenant_id)
        model.scene_config = scene_config
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return model

    def get_scene_config(self, tenant_id: str) -> dict[str, Any]:
        try:
            return self.get(tenant_id).scene_config or {}
        except ValueError:
            return {}
