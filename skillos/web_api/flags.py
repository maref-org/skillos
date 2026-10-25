from __future__ import annotations

from fastapi import APIRouter

from skillos.feature_flags import FeatureFlagManager, FlagState, FlagType

router = APIRouter(tags=["特征开关"])

_manager: FeatureFlagManager | None = None


def _get() -> FeatureFlagManager:
    global _manager
    if _manager is None:
        _manager = FeatureFlagManager()
    return _manager


@router.get("/flags")
async def list_flags():
    m = _get()
    flags = m.list_flags()
    return {
        "flags": [
            {
                "name": getattr(f, "name", f.get("name", "")) if isinstance(f, dict) else str(f),
                "flag_type": (
                    getattr(f, "flag_type", f.get("flag_type", "boolean")) if isinstance(f, dict) else "boolean"
                ),
                "state": getattr(f, "state", f.get("state", "disabled")) if isinstance(f, dict) else "disabled",
                "value": getattr(f, "value", f.get("value", {})) if isinstance(f, dict) else {},
            }
            for f in (flags if isinstance(flags, list) else [])
        ],
        "total": len(flags) if isinstance(flags, list) else 0,
    }


@router.post("/flags")
async def create_flag(name: str, flag_type: str = "boolean", value: str = "true"):
    m = _get()
    m.create_flag(name, FlagType(flag_type), FlagState(value))
    return {"status": "created", "name": name}


@router.put("/flags/{name}")
async def update_flag(name: str, value: str):
    m = _get()
    m.update_flag(name, FlagState(value))
    return {"status": "updated", "name": name}


@router.delete("/flags/{name}")
async def delete_flag(name: str):
    m = _get()
    m.delete_flag(name)
    return {"status": "deleted", "name": name}
