from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.kernel.slo import get_slo_manager
from skillos.observability.metrics import get_metrics
from skillos.observability.slo_alerts import SloAlertService
from skillos.observability.slo_snapshots import SloSnapshotService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["监控中心"])


def _capture_and_evaluate(db: Session, slo_name: str | None = None) -> None:
    """落 SLO 快照并推进告警状态机（M11）。异常不影响主流程。"""
    try:
        SloSnapshotService(db).capture([slo_name] if slo_name else None)
        summary = get_slo_manager().get_slo_summary()
        names = [slo_name] if slo_name else list(summary.keys())
        alert_svc = SloAlertService(db)
        for name in names:
            item = summary.get(name)
            if not isinstance(item, dict):
                continue
            eb = item.get("error_budget", {})
            alert_svc.evaluate(name, eb.get("status", "healthy"), eb.get("remaining_pct", 0.0))
    except Exception as exc:  # noqa: BLE001 可观测性路径失败不影响请求
        logger.warning("SLO capture/evaluate failed: %s", exc)


@router.get("/monitoring/overview")
async def overview(db: Session = Depends(get_session)):
    _capture_and_evaluate(db)
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
    _capture_and_evaluate(db)
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
    _capture_and_evaluate(db, slo_name)
    return service.get_trend(slo_name=slo_name, days=days)


@router.get("/monitoring/alerts/status")
async def alerts_status(db: Session = Depends(get_session)):
    """SLO 告警状态（M11）：各 SLO 当前活跃告警（只读）。"""
    _capture_and_evaluate(db)
    return SloAlertService(db).get_status()


@router.get("/monitoring/alerts/events")
async def alerts_events(
    slo_name: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """SLO 告警事件历史（M11，只读）。"""
    return SloAlertService(db).list_events(slo_name=slo_name, limit=limit)


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
