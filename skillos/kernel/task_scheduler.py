#!/usr/bin/env python3
"""Task Scheduler — 定时任务调度器

职责:
  - 基于 cron 表达式的定时任务调度
  - 任务执行跟踪与统计
  - 任务启用/禁用管理
  - 持久化任务配置
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from croniter import croniter  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = "data/scheduled_tasks.json"


_ALLOWED_HANDLERS = frozenset(
    {
        # 池额度回收调度入口（M13-P1）
        "skillos.market.pool_reclaim:reclaim_scheduled",
        "skillos.market.pool_reclaim.reclaim_scheduled",
        # SLO 告警评估（M11-P1/M13 维护窗口周期化）
        "skillos.observability.slo_alerts.evaluate",
        # 测试桩（仅测试使用，无害纯函数）
        "skillos.market.pool_reclaim:_demo_handler",
    }
)


def is_allowed_handler(handler: str) -> bool:
    """I8 修复：handler 精确函数白名单。

    阻止通过 scheduler API 注册任意 ``module:function``（RCE 面）。
    与前缀放行不同，这里只允许**枚举的精确 handler**，避免
    ``skillos.db.engine:reset_db`` 等包内破坏性函数被调度执行。
    """
    if not handler or not handler.strip():
        return True  # 空 handler 由调用方短路处理
    return handler in _ALLOWED_HANDLERS


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    cron_expression: str
    handler: str
    params: dict[str, Any]
    enabled: bool = True
    last_run: str | None = None
    next_run: str | None = None
    success_count: int = 0
    failure_count: int = 0
    last_error: str | None = None


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self, config_path: str = _DEFAULT_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: asyncio.Task | None = None
        self._load_tasks()

    def _load_tasks(self) -> None:
        """加载已配置的定时任务"""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                    for task_data in data:
                        self.tasks[task_data["task_id"]] = ScheduledTask(**task_data)
                logger.info("Loaded %d scheduled tasks", len(self.tasks))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Failed to load scheduled tasks: %s", e)

    def _save_tasks(self) -> None:
        """保存任务配置"""
        data = [
            {
                "task_id": t.task_id,
                "name": t.name,
                "cron_expression": t.cron_expression,
                "handler": t.handler,
                "params": t.params,
                "enabled": t.enabled,
                "last_run": t.last_run,
                "next_run": t.next_run,
                "success_count": t.success_count,
                "failure_count": t.failure_count,
                "last_error": t.last_error,
            }
            for t in self.tasks.values()
        ]
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _parse_cron(cron_expression: str, now: datetime) -> datetime | None:
        """解析 cron 表达式并计算下次执行时间（M7：now 统一 UTC aware）。"""
        try:
            cron = croniter(cron_expression, now)
            return cron.get_next(datetime)
        except (ValueError, KeyError) as e:
            logger.error("Invalid cron expression '%s': %s", cron_expression, e)
            return None

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        """解析任务时间戳；旧数据无 tz 按 UTC 兜底。"""
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def add_task(
        self,
        task_id: str,
        name: str,
        cron_expression: str,
        handler: str,
        params: dict[str, Any] | None = None,
    ) -> ScheduledTask:
        """添加定时任务"""
        now = self._utcnow()
        next_run = self._parse_cron(cron_expression, now)
        if next_run is None:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        task = ScheduledTask(
            task_id=task_id,
            name=name,
            cron_expression=cron_expression,
            handler=handler,
            params=params or {},
            next_run=next_run.isoformat(),
        )
        self.tasks[task_id] = task
        self._save_tasks()
        logger.info("Scheduled task added: %s (next run: %s)", task_id, next_run)
        return task

    def remove_task(self, task_id: str) -> bool:
        """移除定时任务"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save_tasks()
            logger.info("Scheduled task removed: %s", task_id)
            return True
        return False

    def enable_task(self, task_id: str) -> bool:
        """启用定时任务"""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = True
            self._save_tasks()
            return True
        return False

    def disable_task(self, task_id: str) -> bool:
        """禁用定时任务"""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = False
            self._save_tasks()
            return True
        return False

    def get_task(self, task_id: str) -> ScheduledTask | None:
        """获取任务"""
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        """列出所有任务"""
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "cron_expression": t.cron_expression,
                "handler": t.handler,
                "enabled": t.enabled,
                "last_run": t.last_run,
                "next_run": t.next_run,
                "success_count": t.success_count,
                "failure_count": t.failure_count,
                "last_error": t.last_error,
            }
            for t in self.tasks.values()
        ]

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Task scheduler started")

    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                logger.warning("Task scheduler cancelled")
        logger.info("Task scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """调度循环"""
        while self._running:
            now = self._utcnow()
            due_tasks = []

            for task in self.tasks.values():
                if not task.enabled or not task.next_run:
                    continue

                next_run_time = self._parse_utc(task.next_run)
                if next_run_time <= now:
                    due_tasks.append(task)

            for task in due_tasks:
                await self._execute_task(task)

                new_next = self._parse_cron(task.cron_expression, self._utcnow())
                if new_next:
                    task.next_run = new_next.isoformat()
                else:
                    task.enabled = False
                    logger.error("Failed to calculate next run for task %s", task.task_id)

            self._save_tasks()
            await asyncio.sleep(30)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """执行单个任务"""
        logger.info("Executing scheduled task: %s (%s)", task.task_id, task.handler)
        task.last_run = self._utcnow().isoformat()
        try:
            result = await self._invoke_handler(task.handler, task.params)
            task.success_count += 1
            logger.info("Task %s executed successfully: %s", task.task_id, result)
        except Exception as e:
            task.failure_count += 1
            task.last_error = str(e)
            logger.exception("Task %s failed", task.task_id)

    async def _invoke_handler(self, handler: str, params: dict[str, Any]) -> Any:
        """调用处理器（M13-P1）。

        handler 形如 `module.path:function` 或 `module.path.function`，
        按 dot 路径动态导入并调用（同步或 async 均可，统一 await）。
        无法解析/调用失败时返回错误 dict（不抛错，交给 _execute_task 计数）。

        I8 修复：handler 仅允许 `skillos.` 包内函数（白名单），
        阻止注册/执行任意模块路径（RCE 防护）。
        """
        if not handler or not handler.strip():
            return {"handler": handler, "params": params, "status": "executed"}
        if not is_allowed_handler(handler):
            logger.error("Handler not allowed (RCE guard): %s", handler)
            return {"handler": handler, "params": params, "status": "error", "error": "handler not in whitelist"}
        try:
            module_name, sep, func_name = handler.partition(":")
            if not sep:
                module_name, func_name = handler.rsplit(".", 1)
            import importlib

            module = importlib.import_module(module_name)
            func = getattr(module, func_name)
            result = func(**params) if params else func()
            if asyncio.iscoroutine(result):
                result = await result
            return {"handler": handler, "params": params, "status": "executed", "result": result}
        except Exception as exc:  # noqa: BLE001 调度任务失败仅记录
            logger.exception("Handler %s failed", handler)
            return {"handler": handler, "params": params, "status": "error", "error": str(exc)}
