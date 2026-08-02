from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from skillos.kernel.agent_scheduler import AgentScheduler
from skillos.kernel.skill_kernel import SkillKernel

router = APIRouter(tags=["技能管理"])

logger = logging.getLogger(__name__)

_kernel: SkillKernel | None = None
_scheduler: AgentScheduler | None = None


def _get_kernel() -> SkillKernel:
    global _kernel
    if _kernel is None:
        _kernel = SkillKernel()
    return _kernel


def _get_scheduler() -> AgentScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler


@router.get("/skills")
async def list_skills():
    kernel = _get_kernel()
    skills = kernel.list_skills()
    return {
        "skills": [
            {
                "id": s.get("id", "") if isinstance(s, dict) else str(getattr(s, "id", "")),
                "name": s.get("name", "") if isinstance(s, dict) else str(getattr(s, "name", "")),
                "version": s.get("version", "1.0.0") if isinstance(s, dict) else "1.0.0",
                "status": s.get("status", "unknown") if isinstance(s, dict) else "unknown",
            }
            for s in (skills if isinstance(skills, list) else [])
        ],
        "total": len(skills) if isinstance(skills, list) else 0,
    }


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    kernel = _get_kernel()
    skill = kernel.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"skill": skill}


@router.post("/skills/{skill_id}/execute")
async def execute_skill(skill_id: str):
    kernel = _get_kernel()
    try:
        from skillos.kernel.skill_kernel import ToolChain
        result = await kernel.execute(
            ToolChain(skill_id=skill_id, tools=[], mcp_connectors=[], a2a_adapters=[]),
            {},
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.exception("Skill %s execution failed", skill_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nfts")
async def list_nfts():
    kernel = _get_kernel()
    nfts = getattr(kernel, "_nft_records", [])
    return {
        "nfts": [
            {
                "token_id": getattr(n, "token_id", ""),
                "skill_id": getattr(n, "skill_id", ""),
                "owner": getattr(n, "owner", ""),
                "minted_at": str(getattr(n, "minted_at", "")),
            }
            for n in nfts
        ],
        "total": len(nfts),
    }
