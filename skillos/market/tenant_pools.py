"""Tenant Pool Service — 跨租户共享额度池（M11-P2）

多个租户可加入同一共享池，从池的剩余额度（total_limit - used）按 share_ratio
借用出款额度。池额度调整走审批流（pending → approved/rejected）。

与 PayoutService 集成：出款限额校验升级为「租户自有 → 池共享余额」联合判断。
无池租户行为不变（退回自有限额逻辑）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.models import PoolAdjustmentModel, TenantPoolMemberModel, TenantPoolModel

logger = logging.getLogger(__name__)


class PoolNotFoundError(Exception):
    """池不存在时抛出。"""


class PoolLimitExceededError(Exception):
    """池共享余额不足时抛出（联合校验失败）。"""


class TenantPoolService:
    """共享额度池 CRUD + 成员 + 审批流 + 余额校验。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def create(self, pool_id: str, name: str = "", total_limit: float = 0.0) -> TenantPoolModel:
        if total_limit < 0:
            raise ValueError(f"total_limit cannot be negative: {total_limit}")
        if self.get(pool_id) is not None:
            raise ValueError(f"Pool already exists: {pool_id}")
        now = datetime.now(timezone.utc)
        model = TenantPoolModel(
            pool_id=pool_id,
            name=name,
            total_limit=total_limit,
            used=0.0,
            created_at=now,
            updated_at=now,
        )
        self._db.add(model)
        self._db.flush()
        return model

    def get(self, pool_id: str) -> TenantPoolModel | None:
        return self._db.query(TenantPoolModel).filter(TenantPoolModel.pool_id == pool_id).first()

    def list(self) -> list[TenantPoolModel]:
        return self._db.query(TenantPoolModel).order_by(TenantPoolModel.created_at.asc()).all()

    def add_member(self, pool_id: str, tenant_id: str, share_ratio: float = 1.0) -> TenantPoolMemberModel:
        if share_ratio < 0:
            raise ValueError(f"share_ratio cannot be negative: {share_ratio}")
        if self.get(pool_id) is None:
            raise PoolNotFoundError(f"Pool not found: {pool_id}")
        existing = (
            self._db.query(TenantPoolMemberModel)
            .filter(TenantPoolMemberModel.pool_id == pool_id, TenantPoolMemberModel.tenant_id == tenant_id)
            .first()
        )
        if existing is not None:
            existing.share_ratio = share_ratio
            self._db.flush()
            return existing
        member = TenantPoolMemberModel(pool_id=pool_id, tenant_id=tenant_id, share_ratio=share_ratio)
        self._db.add(member)
        self._db.flush()
        return member

    def remove_member(self, pool_id: str, tenant_id: str) -> None:
        self._db.query(TenantPoolMemberModel).filter(
            TenantPoolMemberModel.pool_id == pool_id, TenantPoolMemberModel.tenant_id == tenant_id
        ).delete()
        self._db.flush()

    def members(self, pool_id: str) -> list[TenantPoolMemberModel]:
        return (
            self._db.query(TenantPoolMemberModel).filter(TenantPoolMemberModel.pool_id == pool_id).all()
        )

    def set_limit(self, pool_id: str, new_limit: float, requested_by: str = "") -> PoolAdjustmentModel:
        """发起池额度调整申请（pending 待审批）。"""
        if new_limit < 0:
            raise ValueError(f"new_limit cannot be negative: {new_limit}")
        if self.get(pool_id) is None:
            raise PoolNotFoundError(f"Pool not found: {pool_id}")
        adj = PoolAdjustmentModel(
            pool_id=pool_id,
            new_limit=new_limit,
            status="pending",
            requested_by=requested_by,
        )
        self._db.add(adj)
        self._db.flush()
        return adj

    def approve(self, adjustment_id: str, approved_by: str = "") -> PoolAdjustmentModel:
        """审批通过：应用 new_limit 到池，置 approved。"""
        adj = self._require_adjustment(adjustment_id)
        if adj.status != "pending":
            raise ValueError(f"Adjustment not pending: {adj.status}")
        pool = self.get(adj.pool_id)
        if pool is None:
            raise PoolNotFoundError(f"Pool not found: {adj.pool_id}")
        pool.total_limit = adj.new_limit
        pool.updated_at = datetime.now(timezone.utc)
        adj.status = "approved"
        adj.approved_by = approved_by
        adj.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return adj

    def reject(self, adjustment_id: str, approved_by: str = "") -> PoolAdjustmentModel:
        """审批驳回：保持池原值，置 rejected。"""
        adj = self._require_adjustment(adjustment_id)
        if adj.status != "pending":
            raise ValueError(f"Adjustment not pending: {adj.status}")
        adj.status = "rejected"
        adj.approved_by = approved_by
        adj.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return adj

    def pool_for_tenant(self, tenant_id: str) -> tuple[TenantPoolModel, TenantPoolMemberModel] | None:
        """返回租户所属的第一个池及其成员关系。"""
        member = (
            self._db.query(TenantPoolMemberModel).filter(TenantPoolMemberModel.tenant_id == tenant_id).first()
        )
        if member is None:
            return None
        pool = self.get(member.pool_id)
        return (pool, member) if pool is not None and pool.status == "active" else None

    def check_available(self, pool_id: str, tenant_id: str) -> float:
        """返回租户从池可借用的剩余额度。"""
        rel = self.pool_for_tenant(tenant_id)
        if rel is None or rel[0].pool_id != pool_id:
            return 0.0
        pool, member = rel
        return max(0.0, pool.total_limit - pool.used) * member.share_ratio

    def consume(self, pool_id: str, tenant_id: str, amount: float) -> bool:
        """尝试从池借用 amount 额度。成功返回 True 并扣减池 used。"""
        rel = self.pool_for_tenant(tenant_id)
        if rel is None or rel[0].pool_id != pool_id:
            return False
        pool, member = rel
        pool_remaining = max(0.0, pool.total_limit - pool.used)
        share_available = pool_remaining * member.share_ratio
        if amount > share_available:
            return False
        pool.used = round(pool.used + amount, 2)
        pool.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return True

    def _require_adjustment(self, adjustment_id: str) -> PoolAdjustmentModel:
        adj = self._db.query(PoolAdjustmentModel).filter(PoolAdjustmentModel.id == adjustment_id).first()
        if adj is None:
            raise ValueError(f"Adjustment not found: {adjustment_id}")
        return adj

    def serialize(self, pool: TenantPoolModel) -> dict[str, Any]:
        return {
            "pool_id": pool.pool_id,
            "name": pool.name,
            "total_limit": pool.total_limit,
            "used": pool.used,
            "remaining": round(max(0.0, pool.total_limit - pool.used), 2),
            "status": pool.status,
            "members": [m.tenant_id for m in self.members(pool.pool_id)],
            "created_at": pool.created_at.isoformat() if pool.created_at else None,
        }
