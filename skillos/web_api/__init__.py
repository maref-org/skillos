from fastapi import APIRouter

from skillos.web_api.agent import router as agent_router
from skillos.web_api.economics import router as economics_router
from skillos.web_api.flags import router as flags_router
from skillos.web_api.monitoring import router as monitoring_router
from skillos.web_api.onboarding import router as onboarding_router
from skillos.web_api.protocol import router as protocol_router
from skillos.web_api.scheduler import router as scheduler_router
from skillos.web_api.security import router as security_router
from skillos.web_api.sessions import router as sessions_router
from skillos.web_api.skills import router as skills_router
from skillos.web_api.system import router as system_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(monitoring_router)
api_router.include_router(skills_router)
api_router.include_router(sessions_router)
api_router.include_router(economics_router)
api_router.include_router(security_router)
api_router.include_router(flags_router)
api_router.include_router(system_router)
api_router.include_router(scheduler_router)
api_router.include_router(protocol_router)
api_router.include_router(onboarding_router)
api_router.include_router(agent_router)
