from __future__ import annotations

from fastapi import APIRouter

from skillos.distribution.engine import DistributionEngine

router = APIRouter(tags=["经济模型"])

_engine: DistributionEngine | None = None


def _get() -> DistributionEngine:
    global _engine
    if _engine is None:
        _engine = DistributionEngine()
    return _engine


@router.get("/economics/overview")
async def economics_overview():
    eng = _get()
    log = getattr(eng, "_distribution_log", [])
    contributors = getattr(eng, "_contributor_registry", {})
    total_revenue = sum(getattr(r, "total_amount", 0) for r in log)
    total_platform = sum(getattr(r, "platform_fee", 0) for r in log)
    total_contributor = sum(getattr(r, "contributor_pool", 0) for r in log)
    return {
        "total_distributions": len(log),
        "total_revenue": round(total_revenue, 4),
        "total_platform_fee": round(total_platform, 4),
        "total_contributor_pool": round(total_contributor, 4),
        "contributor_count": len(contributors),
    }


@router.get("/economics/records")
async def distribution_records():
    eng = _get()
    log = getattr(eng, "_distribution_log", [])
    return {
        "records": [
            {
                "id": getattr(r, "id", "") or getattr(r, "call_id", ""),
                "total_amount": getattr(r, "total_amount", 0),
                "platform_fee": getattr(r, "platform_fee", 0),
                "ecosystem_fee": getattr(r, "ecosystem_fee", 0),
                "contributor_pool": getattr(r, "contributor_pool", 0),
            }
            for r in log
        ],
        "total": len(log),
    }


@router.get("/economics/contributors")
async def list_contributors():
    eng = _get()
    contributors = getattr(eng, "_contributor_registry", {})
    return {
        "contributors": [
            {
                "id": cid,
                "name": getattr(c, "name", cid),
                "weight": getattr(c, "computed_weight", 0) if hasattr(c, "computed_weight") else 0,
            }
            for cid, c in contributors.items()
        ],
        "total": len(contributors),
    }


@router.post("/economics/register")
async def register_contributor(contributor_id: str, name: str = ""):
    eng = _get()
    from skillos.types import Contributor

    eng.register_contributor(Contributor(contributor_id=contributor_id, name=name or contributor_id))
    return {"status": "registered", "contributor_id": contributor_id}
