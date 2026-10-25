#!/usr/bin/env python3
"""SkillOS FastAPI 应用 — RED 指标 + SLO 采集中间件

职责：
  - 挂载 negmarket.router 等现有 APIRouter
  - 通过 ASGI 中间件自动采集 RED 指标（Rate / Errors / Duration）
  - 记录 SLO 延迟（negmarket_api / protocol_gateway）
  - 暴露 /metrics 端点供 Prometheus 抓取

依赖：
  - FastAPI / Starlette（可选，通过 ``pip install skillos[web]`` 安装）
  - prometheus-client（可选，未安装时 MetricsCollector 以 no-op 模式运行）

使用示例::

    from skillos.app import create_app
    app = create_app()
    # uvicorn skillos.app:app --host 0.0.0.0 --port 8080
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def create_app() -> Any:
    """创建并返回配置了 RED 中间件的 FastAPI 应用。

    Returns:
        FastAPI: 配置好的 FastAPI 应用实例

    Raises:
        ImportError: FastAPI 未安装时抛出（安装: ``pip install skillos[web]``）
    """
    try:
        from fastapi import FastAPI, Request, Response
        from starlette.middleware.base import BaseHTTPMiddleware
    except ImportError as exc:
        raise ImportError("FastAPI is not installed. Install with: pip install skillos[web]") from exc

    from skillos.kernel.slo import get_slo_manager
    from skillos.observability.metrics import get_metrics

    app = FastAPI(
        title="SkillOS",
        description="Skill Operating System — Agent 技能调度与编排",
        version="0.6.0-beta.1",
    )

    metrics = get_metrics()
    slo = get_slo_manager()

    # ── 应用启动审计事件 ──────────────────────────────────────────────────
    @app.on_event("startup")
    async def log_startup():
        try:
            from skillos.audit import AuditEventType, get_audit_logger

            audit = get_audit_logger()
            audit.log(AuditEventType.SYSTEM_ERROR, "system", "skillos", "Application started")
        except Exception:
            logger.warning("startup audit log failed", exc_info=True)

    # ── RED 中间件 ────────────────────────────────────────────────────
    class REDMiddleware(BaseHTTPMiddleware):
        """自动采集每个 HTTP 请求的 RED 指标 + SLO 延迟。"""

        async def dispatch(self, request: Request, call_next: Any) -> Response:
            endpoint = request.url.path
            start = time.monotonic()

            try:
                response = await call_next(request)
                duration = time.monotonic() - start

                # RED: Rate + Duration
                metrics.record_request(endpoint, response.status_code, duration)

                # SLO: negmarket_api 延迟
                if endpoint.startswith("/negmarket"):
                    slo.record_latency("negmarket_api", duration * 1000)
                    slo.record_availability("negmarket_api", response.status_code < 500)

                # 错误计数
                if response.status_code >= 500:
                    metrics.record_error("server_error")

                return response
            except Exception as exc:
                duration = time.monotonic() - start
                metrics.record_request(endpoint, 500, duration)
                metrics.record_error(type(exc).__name__)
                # 仅 negmarket 端点的异常计入 negmarket_api SLO（与成功分支一致）
                if endpoint.startswith("/negmarket"):
                    slo.record_latency("negmarket_api", duration * 1000)
                    slo.record_availability("negmarket_api", False)
                raise

    app.add_middleware(REDMiddleware)

    # ── /metrics 端点 ─────────────────────────────────────────────────
    @app.get("/metrics", tags=["observability"])
    async def prometheus_metrics() -> Response:
        """Prometheus 抓取端点。"""
        return Response(
            content=metrics.get_metrics_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # ── 根路由 ────────────────────────────────────────────────────────
    @app.get("/", tags=["observability"])
    async def root() -> dict[str, str]:
        """服务入口信息（避免 DAST/爬虫在根路径得到 404）。"""
        return {"service": "skillos", "version": "0.6.0-beta.1", "docs": "/docs"}

    # ── /health 端点 ──────────────────────────────────────────────────
    @app.get("/health", tags=["observability"])
    async def health_check() -> dict[str, Any]:
        """健康检查端点。"""
        return {
            "status": "healthy",
            "version": "0.6.0-beta.1",
            "slo_summary": slo.get_slo_summary(),
        }

    # ── 挂载现有 APIRouter ────────────────────────────────────────────
    try:
        from skillos.negmarket.api import router as negmarket_router

        app.include_router(negmarket_router)
        logger.info("Mounted negmarket router at /negmarket")
    except ImportError as exc:
        logger.warning("negmarket router not available: %s", exc)

    # ── CSWDP ─────────────────────────────────────────────────────────
    try:
        from skillos.cswdp.api import router as cswdp_router

        app.include_router(cswdp_router)
        logger.info("Mounted CSWDP router at /cswdp")
    except ImportError as exc:
        logger.warning("CSWDP router not available: %s", exc)

    # ── Market Layer ───────────────────────────────────────────────────
    try:
        from skillos.market.api import router as market_router

        app.include_router(market_router)
        logger.info("Mounted market router at /market")
    except ImportError as exc:
        logger.warning("market router not available: %s", exc)

    # ── SkillOS Web API v1 ────────────────────────────────────────────
    try:
        from skillos.web_api import api_router

        app.include_router(api_router)
        logger.info("Mounted SkillOS Web API at /api/v1")
    except ImportError as exc:
        logger.warning("SkillOS Web API not available: %s", exc)

    return app


# 模块级 app 实例（供 uvicorn skillos.app:app 使用）
try:
    app = create_app()
except ImportError:
    # FastAPI 未安装时不阻止导入（允许其他模块引用 app 模块）
    app = None  # type: ignore[assignment]
    logger.warning("FastAPI not installed. skillos.app.app is None. Install with: pip install skillos[web]")
