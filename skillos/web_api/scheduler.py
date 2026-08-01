"""Scheduler API — 定时任务管理（M13-P1）

挂接 `TaskScheduler`（cron 调度），handler 形如 `module:function` 或
`module.function`，按 dot 路径动态导入调用。

端点一览::

    POST   /scheduler/tasks          # 注册定时任务（签名）
    GET    /scheduler/tasks          # 任务列表（只读）
    DELETE /scheduler/tasks/{id}     # 移除任务（签名）
    POST   /scheduler/tasks/{id}/enable    # 启用（签名）
    POST   /scheduler/tasks/{id}/disable   # 禁用（签名）
    POST   /pools/reclaim            # 手动触发池额度回收（签名，M13-P1）

鉴权: 复用 MessageSigner（Ed25519），可变端点强制签名者身份。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from skillos.db.engine import get_session
from skillos.db.models import IdentityModel
from skillos.kernel.task_scheduler import TaskScheduler
from skillos.market.pool_reclaim import PoolReclaimService
from skillos.security.message_signer import MessageSigner

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scheduler"])


def _get_scheduler() -> TaskScheduler:
    return TaskScheduler()


def _validate_handler(handler: str) -> None:
    """校验 handler 可动态导入，避免注册了运行时不存在的任务。"""
    if not handler or not handler.strip():
        raise HTTPException(status_code=400, detail="handler 不能为空")
    module_name, sep, func_name = handler.partition(":")
    if not sep:
        try:
            module_name, func_name = handler.rsplit(".", 1)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"handler 格式无效: {handler}") from exc
    import importlib

    try:
        module = importlib.import_module(module_name)
        if not hasattr(module, func_name):
            raise AttributeError(f"{func_name} not found in {module_name}")
    except (ImportError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail=f"handler 无法解析: {handler} ({exc})") from exc


async def _require_actor(request: Request, db: Session = Depends(get_session)) -> str:
    """验证请求签名并返回签名者身份 ID（未通过则 401/403）。"""
    raw = await request.body()
    payload: dict[str, Any] = json.loads(raw) if raw else {}
    headers = {k.lower(): v for k, v in request.headers.items()}
    signer_id = headers.get("x-signer-id", "")
    if not signer_id or not MessageSigner.verify(payload, headers):
        raise HTTPException(status_code=401, detail="invalid or missing signature")
    if not db.query(IdentityModel).filter(IdentityModel.identity_id == signer_id).first():
        raise HTTPException(status_code=403, detail="identity not registered")
    return signer_id


@router.post("/scheduler/tasks")
async def add_scheduler_task(
    request: Request,
    task_id: str = Body(..., min_length=3, max_length=64),
    name: str = Body(..., max_length=128),
    cron_expression: str = Body(..., max_length=128),
    handler: str = Body(..., max_length=256),
    params: dict[str, Any] = Body({}),
    db: Session = Depends(get_session),
):
    """注册 cron 定时任务（handler 须可动态导入）。"""
    await _require_actor(request, db)
    _validate_handler(handler)
    try:
        task = _get_scheduler().add_task(task_id, name, cron_expression, handler, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "task_id": task.task_id, "next_run": task.next_run}


@router.get("/scheduler/tasks")
def list_scheduler_tasks():
    """定时任务列表（只读）。"""
    return {"tasks": _get_scheduler().list_tasks()}


@router.delete("/scheduler/tasks/{task_id}")
async def remove_scheduler_task(task_id: str, request: Request, db: Session = Depends(get_session)):
    """移除定时任务。"""
    await _require_actor(request, db)
    removed = _get_scheduler().remove_task(task_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return {"success": True, "task_id": task_id}


@router.post("/scheduler/tasks/{task_id}/enable")
async def enable_scheduler_task(task_id: str, request: Request, db: Session = Depends(get_session)):
    """启用定时任务。"""
    await _require_actor(request, db)
    if not _get_scheduler().enable_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return {"success": True, "task_id": task_id, "enabled": True}


@router.post("/scheduler/tasks/{task_id}/disable")
async def disable_scheduler_task(task_id: str, request: Request, db: Session = Depends(get_session)):
    """禁用定时任务。"""
    await _require_actor(request, db)
    if not _get_scheduler().disable_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return {"success": True, "task_id": task_id, "enabled": False}


@router.post("/pools/reclaim")
async def reclaim_pool_quota(
    request: Request,
    db: Session = Depends(get_session),
):
    """手动触发池额度自动回收（M13-P1）。"""
    await _require_actor(request, db)
    result = PoolReclaimService(db).reclaim()
    return {"success": True, **result}
