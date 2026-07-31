from __future__ import annotations

from fastapi import APIRouter

from skillos.kernel.error_codes import list_codes as list_error_codes
from skillos.kernel.task_scheduler import TaskScheduler
from skillos.version import __version__

router = APIRouter(tags=["系统配置"])

_scheduler: TaskScheduler | None = None


def _get_scheduler() -> TaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


@router.get("/system/version")
async def system_version():
    return {
        "version": __version__,
        "python": "3.11+",
    }


@router.get("/system/error-codes")
async def error_codes():
    codes = list_error_codes()
    return {
        "codes": [
            {
                "code": getattr(c, "code", ""),
                "message": getattr(c, "message", ""),
                "category": str(getattr(c, "category", "unknown")),
            }
            for c in codes
        ],
        "total": len(codes),
    }


@router.get("/system/tasks")
async def scheduled_tasks():
    s = _get_scheduler()
    tasks = getattr(s, "tasks", {})
    return {
        "tasks": [
            {
                "task_id": tid,
                "name": getattr(t, "name", tid),
                "cron": getattr(t, "cron_expression", ""),
                "enabled": getattr(t, "enabled", False),
                "last_run": str(getattr(t, "last_run", "")),
            }
            for tid, t in tasks.items()
        ],
        "total": len(tasks),
    }
