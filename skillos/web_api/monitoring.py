from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.kernel.slo import get_slo_manager
from skillos.observability.metrics import get_metrics
from skillos.observability.slo_snapshots import SloSnapshotService

router = APIRouter(tags=["监控中心"])


@router.get("/monitoring/overview")
async def overview(db: Session = Depends(get_session)):
    SloSnapshotService(db).capture()
    slo = get_slo_manager()
    slo_summary = slo.get_slo_summary()
    healthy_count = sum(
        1 for s in slo_summary.values()
        if isinstance(s, dict) and s.get("error_budget", {}).get("status") == "healthy"
    )
    return {
        "total_slos": len(slo_summary),
        "healthy_slos": healthy_count,
        "error_rate": 0.05,
        "active_sessions": 0,
        "total_skills": 0,
        "version": "0.6.0-beta",
        "uptime_seconds": time.time(),
    }


@router.get("/monitoring/slo")
async def slo_summary(db: Session = Depends(get_session)):
    SloSnapshotService(db).capture()
    slo = get_slo_manager()
    return slo.get_slo_summary()


@router.get("/monitoring/slo/trend")
async def slo_trend(
    slo_name: str | None = Query(None),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_session),
):
    """SLO 趋势曲线（M10）：近 N 天按日聚合的错误预算剩余百分比。

    slo_name 缺省返回全部 SLO：{slo_name: [{date, remaining_pct, status}]}。
    查询前自动捕获当前快照，保证趋势包含最新状态。
    """
    service = SloSnapshotService(db)
    service.capture([slo_name] if slo_name else None)
    return service.get_trend(slo_name=slo_name, days=days)


@router.get("/monitoring/metrics")
async def metrics_snapshot():
    metrics = get_metrics()
    return {
        "requests_total": (
            metrics.skillos_requests_total._value.get()
            if hasattr(metrics, "skillos_requests_total")
            else 0
        ),
        "errors_total": (
            metrics.skillos_errors_total._value.get()
            if hasattr(metrics, "skillos_errors_total")
            else 0
        ),
        "active_sessions": (
            metrics.skillos_session_active_count._value.get()
            if hasattr(metrics, "skillos_session_active_count")
            else 0
        ),
    }
