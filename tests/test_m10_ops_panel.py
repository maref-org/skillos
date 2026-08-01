"""Tests for M10 — SLO 趋势曲线 + 平台级跨租户风控面板

覆盖：
  - SloSnapshotService.capture 落库
  - SloSnapshotService.get_trend 按日聚合取末条
  - GET /monitoring/slo/trend 端点
  - GET /outcome/platform-risk 端点（汇总/超限/高风险）
"""

import pytest

pytest.importorskip("fastapi")

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.db.models import SloSnapshotModel
from skillos.kernel.slo import get_slo_manager, reset_slo_manager
from skillos.market.tenants import TenantService
from skillos.observability.slo_snapshots import SloSnapshotService
from skillos.web_api.monitoring import router as monitoring_router
from skillos.web_api.outcome import router as outcome_router


@pytest.fixture(autouse=True)
def _reset_slo():
    reset_slo_manager()
    yield
    reset_slo_manager()


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(monitoring_router)
    app.include_router(outcome_router)
    return TestClient(app)


class TestSloSnapshotService:
    def test_capture_persists_snapshots(self, db_session):
        get_slo_manager().record_availability("negmarket_api", True)
        n = SloSnapshotService(db_session).capture(["negmarket_api"])
        assert n == 1
        rows = db_session.query(SloSnapshotModel).filter(SloSnapshotModel.slo_name == "negmarket_api").all()
        assert len(rows) == 1
        assert rows[0].remaining_pct > 0
        assert rows[0].status in ("healthy", "at_risk", "burning", "exhausted")

    def test_capture_all_slos(self, db_session):
        n = SloSnapshotService(db_session).capture()
        names = {r.slo_name for r in db_session.query(SloSnapshotModel).all()}
        assert n == 4  # skill_call/protocol_gateway/negmarket_api/kernel_routing
        assert names == {"skill_call", "protocol_gateway", "negmarket_api", "kernel_routing"}

    def test_get_trend_no_data_empty(self, db_session):
        trend = SloSnapshotService(db_session).get_trend("negmarket_api", days=7)
        assert trend == []

    def test_get_trend_aggregates_latest_per_day(self, db_session):
        service = SloSnapshotService(db_session)
        # 同一天两条快照 → 取末条
        day = datetime.now(timezone.utc)
        db_session.add_all(
            [
                SloSnapshotModel(slo_name="negmarket_api", status="healthy", remaining_pct=60.0, sampled_at=day),
                SloSnapshotModel(slo_name="negmarket_api", status="burning", remaining_pct=20.0, sampled_at=day),
            ]
        )
        db_session.flush()
        trend = service.get_trend("negmarket_api", days=7)
        assert len(trend) == 1
        assert trend[0]["remaining_pct"] == 20.0
        assert trend[0]["status"] == "burning"

    def test_get_trend_all_slos_grouped(self, db_session):
        day = datetime.now(timezone.utc)
        db_session.add_all(
            [
                SloSnapshotModel(slo_name="negmarket_api", status="healthy", remaining_pct=90.0, sampled_at=day),
                SloSnapshotModel(slo_name="kernel_routing", status="exhausted", remaining_pct=0.0, sampled_at=day),
            ]
        )
        db_session.flush()
        trend = SloSnapshotService(db_session).get_trend(days=7)
        assert set(trend.keys()) == {"negmarket_api", "kernel_routing"}
        assert trend["negmarket_api"][0]["remaining_pct"] == 90.0
        assert trend["kernel_routing"][0]["status"] == "exhausted"


class TestSloTrendApi:
    def test_trend_endpoint(self, client):
        get_slo_manager().record_availability("negmarket_api", True)
        r = client.get("/monitoring/slo/trend?slo_name=negmarket_api&days=7")
        assert r.status_code == 200
        body = r.json()
        # capture 会在查询前落一条快照 → 至少有 1 个点
        assert isinstance(body, list)
        assert len(body) >= 1
        point = body[-1]
        assert "date" in point and "remaining_pct" in point and "status" in point

    def test_trend_all_slos(self, client):
        r = client.get("/monitoring/slo/trend")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)
        assert "negmarket_api" in body


class TestPlatformRiskApi:
    @staticmethod
    def _mk_tenant(db_session, tenant_id, limit, used):
        ts = TenantService(db_session)
        try:
            ts.get(tenant_id)
        except ValueError:
            ts.create(tenant_id, tenant_id)
        ts.set_payout_quota(tenant_id, limit)
        ts.add_payout_used(tenant_id, used)

    def test_empty_db(self, client):
        r = client.get("/outcome/platform-risk")
        assert r.status_code == 200
        body = r.json()
        assert body["tenant_count"] == 0
        assert body["total_limit"] == 0.0
        assert body["over_limit"] == []
        assert body["at_risk"] == []

    def test_aggregates_and_identifies_risk(self, client, db_session):
        self._mk_tenant(db_session, "t-ok", 10000, 3000)       # 30% 正常
        self._mk_tenant(db_session, "t-over", 5000, 6000)      # 超限
        self._mk_tenant(db_session, "t-risk", 10000, 8500)     # 85% 高风险
        r = client.get("/outcome/platform-risk")
        assert r.status_code == 200
        body = r.json()
        assert body["tenant_count"] == 3
        assert body["total_limit"] == 25000.0
        assert body["total_used"] == 17500.0
        assert body["utilization_pct"] == 70.0
        assert [o["tenant_id"] for o in body["over_limit"]] == ["t-over"]
        assert [o["tenant_id"] for o in body["at_risk"]] == ["t-risk"]

    def test_unlimited_tenants_excluded(self, client, db_session):
        ts = TenantService(db_session)
        ts.create("t-nolimit", "no limit")  # 不限额不参与统计
        r = client.get("/outcome/platform-risk")
        assert r.status_code == 200
        assert r.json()["tenant_count"] == 0
