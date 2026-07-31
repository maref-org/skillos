from __future__ import annotations

from fastapi import APIRouter, HTTPException

from skillos.kernel.session_manager import SessionManager

router = APIRouter(tags=["会话管理"])

_manager: SessionManager | None = None


def _get() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


@router.get("/sessions")
async def list_sessions(user_id: str | None = None):
    m = _get()
    sessions = m.list_sessions(user_id=user_id) if user_id else m.list_sessions()
    return {
        "sessions": [
            {
                "id": s.session_id if not isinstance(s, dict) else s.get("session_id", ""),
                "user_id": s.user_id if not isinstance(s, dict) else s.get("user_id", ""),
                "status": s.status.value if not isinstance(s, dict) else s.get("status", "active"),
            }
            for s in (sessions if isinstance(sessions, list) else [])
        ],
        "total": len(sessions) if isinstance(sessions, list) else 0,
    }


@router.get("/sessions/stats")
async def session_stats():
    m = _get()
    stats = m.get_session_stats() if hasattr(m, "get_session_stats") else {}
    return {"stats": stats}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    m = _get()
    session = m.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session": session}


@router.post("/sessions")
async def create_session(user_id: str = "default"):
    m = _get()
    session = m.create_session(user_id=user_id)
    return {"session_id": getattr(session, "session_id", session) if not isinstance(session, str) else session}


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    m = _get()
    m.pause_session(session_id)
    return {"status": "paused"}


@router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    m = _get()
    m.resume_session(session_id)
    return {"status": "resumed"}


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str):
    m = _get()
    m.complete_session(session_id)
    return {"status": "completed"}


@router.post("/sessions/{session_id}/abort")
async def abort_session(session_id: str):
    m = _get()
    m.abort_session(session_id)
    return {"status": "aborted"}
