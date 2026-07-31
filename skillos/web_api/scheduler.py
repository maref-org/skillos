from __future__ import annotations

from fastapi import APIRouter

from skillos.kernel.agent_scheduler import AgentScheduler

router = APIRouter(tags=["Agent 调度"])

_scheduler: AgentScheduler | None = None


def _get() -> AgentScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler


@router.get("/scheduler/assignments")
async def list_assignments():
    s = _get()
    history = getattr(s, "_assignment_log", [])
    return {
        "assignments": [
            {
                "task_id": getattr(a, "task_id", ""),
                "assigned_model": getattr(a, "assigned_model", ""),
                "model_group": getattr(a, "model_group", ""),
                "estimated_cost": getattr(a, "estimated_cost", 0),
                "estimated_latency": getattr(a, "estimated_latency", 0),
            }
            for a in history
        ],
        "total": len(history),
    }


@router.get("/scheduler/costs")
async def cost_summary():
    s = _get()
    model_map = getattr(s, "MODEL_MAP", {})
    return {
        "total_cost": sum(c.get("cost_per_call", 0) for c in model_map.values()),
        "model_count": len(model_map),
        "models": [
            {
                "tier": tier,
                "name": cfg.get("model", ""),
                "cost": cfg.get("cost_per_call", 0),
                "latency": cfg.get("latency_ms", 0),
            }
            for tier, cfg in model_map.items()
        ],
    }
