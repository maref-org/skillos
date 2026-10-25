"""池额度自动回收服务 — M13-P1

策略：池 used 的来源是「租户自有超限后从池借用」。契约结算后租户自有用量
不再增长，池借用应有机会归还。因池无借出明细（M11 只维护 used 总额），
回收采用「按成员 share_ratio 归还超自有部分」策略：

  对每个活跃池、每个成员，若该租户自有额度不再超限（used < limit），
  则把「超出自有部分」（min(超限额, 池 used × share_ratio)）从池 used 释放。

触发方式：
  - 调度器：挂到 TaskScheduler cron handler（`reclaim_scheduled` 无参入口）
  - 手动：`POST /pools/reclaim`（签名）
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.engine import get_sessionmaker
from skillos.db.models import TenantPoolMemberModel, TenantPoolModel
from skillos.market.tenant_pools import TenantPoolService
from skillos.market.tenants import TenantService

logger = logging.getLogger(__name__)


class PoolReclaimService:
    """池额度自动回收：按成员归还超出自有部分的借用额度。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def reclaim(self) -> dict[str, Any]:
        """执行一次全量回收。返回每个池的实际归还量。

        语义：租户自有额度已不超限（limit>0 且 used <= limit）时，
        此前从池借用（池 used 的一部分）应归还。因无借出明细，
        归还量 = min(自有富余量, 池 used × 该成员 share_ratio)。
        """
        pools = self._db.query(TenantPoolModel).filter(TenantPoolModel.status == "active").all()
        result: dict[str, Any] = {"pools": {}, "total_released": 0.0}
        tenant_svc = TenantService(self._db)
        pool_svc = TenantPoolService(self._db)

        for pool in pools:
            released_for_pool = 0.0
            for member in self._db.query(TenantPoolMemberModel).filter(TenantPoolMemberModel.pool_id == pool.pool_id):
                usage = tenant_svc.get_payout_usage(member.tenant_id)
                limit = usage.get("limit", 0.0)
                used = usage.get("used", 0.0)
                if limit <= 0 or used >= limit:
                    # 未设限或不超限则跳过；已超限仍需保留池借用
                    continue
                surplus = round(limit - used, 2)
                share_cap = round(max(0.0, pool.used) * member.share_ratio, 2)
                release_amount = min(surplus, share_cap)
                if release_amount <= 0:
                    continue
                actual = pool_svc.release(pool.pool_id, member.tenant_id, release_amount)
                if actual > 0:
                    released_for_pool += actual
            if released_for_pool > 0:
                result["pools"][pool.pool_id] = round(released_for_pool, 2)

        result["total_released"] = round(sum(result["pools"].values()), 2)
        logger.info("Pool reclaim: %s", result)
        return result


def reclaim_scheduled() -> dict[str, Any]:
    """供 TaskScheduler 调用的无参入口（自建 session 后执行）。"""
    session = get_sessionmaker()()
    try:
        return PoolReclaimService(session).reclaim()
    finally:
        session.close()


def _demo_handler(x: int = 0) -> int:
    """调度器 handler 接线演示（供测试/示例）。"""
    return x * 2
