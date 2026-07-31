from __future__ import annotations

import time

from fastapi import APIRouter

from skillos.kernel.slo import get_slo_manager
from skillos.observability.metrics import get_metrics

router = APIRouter(tags=["监控中心"])


@router.get("/monitoring/overview")
async def overview():
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
async def slo_summary():
    slo = get_slo_manager()
    return slo.get_slo_summary()


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
