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

    VALID_STATUS = ("draft", "active", "inactive")

    def __init__(self, db_session: Session):
        self._db = db_session

    def create(
        self,
        tenant_id: str,
        name: str = "",
        scene_config: dict[str, Any] | None = None,
        status: str = "draft",
    ) -> TenantModel:
        if status not in self.VALID_STATUS:
            raise ValueError(f"Invalid tenant status: {status}")
        if self._db.query(TenantModel).filter(TenantModel.tenant_id == tenant_id).first() is not None:
            raise ValueError(f"Tenant already exists: {tenant_id}")
        now = datetime.now(timezone.utc)
        model = TenantModel(
            tenant_id=tenant_id,
            name=name,
            status=status,
            scene_config=scene_config or {},
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        self._db.flush()
        return model

    def set_status(self, tenant_id: str, status: str) -> TenantModel:
        if status not in self.VALID_STATUS:
            raise ValueError(f"Invalid tenant status: {status}")
        model = self.get(tenant_id)
        model.status = status
        model.updated_at = datetime.now(timezone.utc)
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

    def set_payout_quota(self, tenant_id: str, payout_limit: float) -> TenantModel:
        """设置租户月出款限额。0 = 不限额；负数拒绝。"""
        if payout_limit < 0:
            raise ValueError(f"payout_limit cannot be negative: {payout_limit}")
        model = self.get(tenant_id)
        model.payout_limit = round(float(payout_limit), 2)
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return model

    def add_payout_used(self, tenant_id: str, amount: float) -> TenantModel:
        """累计租户已用出款额（仅首次生成指令时调用，幂等导出不叠加）。"""
        if amount < 0:
            raise ValueError(f"payout amount cannot be negative: {amount}")
        model = self.get(tenant_id)
        model.payout_used = round(model.payout_used + float(amount), 2)
        model.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return model

    def get_payout_usage(self, tenant_id: str) -> dict[str, Any]:
        """返回租户出款配额使用情况：limit/used/remaining。"""
        model = self.get(tenant_id)
        limit = float(model.payout_limit or 0.0)
        used = float(model.payout_used or 0.0)
        if limit <= 0:
            return {"limit": 0.0, "used": round(used, 2), "remaining": None}
        return {
            "limit": round(limit, 2),
            "used": round(used, 2),
            "remaining": round(max(0.0, limit - used), 2),
        }
