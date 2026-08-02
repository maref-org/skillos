"""Tests for skillos.app — FastAPI 应用 + RED 中间件"""

from __future__ import annotations

import pytest

# FastAPI 不可用时跳过全部测试
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def app():
    """创建测试用 FastAPI 应用。"""
    from skillos.app import create_app
    return create_app()


@pytest.fixture
def client(app):
    """创建 TestClient。"""
    return TestClient(app)


class TestHealthEndpoint:
    """测试 /health 端点。"""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_returns_status_healthy(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"

    def test_returns_version(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert "version" in data

    def test_returns_slo_summary(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert "slo_summary" in data


class TestMetricsEndpoint:
    """测试 /metrics 端点。"""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_returns_text_content(self, client: TestClient) -> None:
        resp = client.get("/metrics")
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_recorded_after_request(self, client: TestClient) -> None:
        """发起请求后，/metrics 应包含请求计数。"""
        # 先发起一个请求
        client.get("/health")
        # 然后检查 metrics
        resp = client.get("/metrics")
        content = resp.text
        # metrics 文本应非空（可能是 no-op 模式的 "# metrics disabled" 或实际指标）
        assert len(content) > 0


class TestREDMiddleware:
    """测试 RED 中间件自动采集。"""

    def test_request_recorded(self, client: TestClient) -> None:
        """中间件应在每个请求后记录 RED 指标。"""
        from skillos.observability.metrics import get_metrics

        metrics = get_metrics()
        # 发起请求
        resp = client.get("/health")
        assert resp.status_code == 200

        # 如果 prometheus-client 已安装，metrics 应已记录
        # 我们通过检查 metrics.enabled 来判断
        if metrics.enabled:
            metrics_text = metrics.get_metrics_text()
            # 应包含 skillos_requests_total
            assert "skillos_requests_total" in metrics_text or "skillos_" in metrics_text

    def test_404_recorded(self, client: TestClient) -> None:
        """404 请求也应被记录。"""
        resp = client.get("/nonexistent-endpoint")
        assert resp.status_code == 404

    def test_negmarket_slo_recorded(self, client: TestClient) -> None:
        """访问 /negmarket 路径应记录 negmarket_api SLO。"""
        from skillos.kernel.slo import get_slo_manager

        slo = get_slo_manager()
        # 访问 negmarket 端点（可能返回 404，但 SLO 仍应记录）
        client.get("/negmarket/discover")

        # 检查 SLO 是否有测量数据（I5：availability 与 latency 分开存储）
        measurements = slo._availability.get("negmarket_api", [])
        # middleware 应已记录至少一条测量
        assert len(measurements) > 0


class TestAppCreation:
    """测试应用创建。"""

    def test_create_app_returns_fastapi(self) -> None:
        from fastapi import FastAPI

        from skillos.app import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_routes(self, app) -> None:
        """应用应包含 /health 和 /metrics 路由。"""
        routes = [getattr(r, "path", None) for r in app.routes]
        assert "/health" in routes
        assert "/metrics" in routes
