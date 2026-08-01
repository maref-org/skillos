"""Tests for M11-P1 — SLO 自动告警推送

覆盖：状态机触发/恢复/去重、无 URL 降级、alerts/status 与 alerts/events 端点。
"""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillos.db.models import SloAlertModel
from skillos.kernel.slo import get_slo_manager, reset_slo_manager
from skillos.observability.slo_alerts import SloAlertService
from skillos.web_api.monitoring import router as monitoring_router


@pytest.fixture(autouse=True)
def _reset_slo(monkeypatch):
    reset_slo_manager()
    monkeypatch.delenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", raising=False)
    yield
    reset_slo_manager()


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(monitoring_router)
    return TestClient(app)


class TestSloAlertStateMachine:
    def test_triggers_on_burning(self, db_session):
        alert = SloAlertService(db_session).evaluate("negmarket_api", "burning", 30.0)
        assert alert is not None
        assert alert.status == "firing"
        assert alert.severity == "warning"

    def test_triggers_on_exhausted_critical(self, db_session):
        alert = SloAlertService(db_session).evaluate("negmarket_api", "exhausted", 0.0)
        assert alert.status == "firing"
        assert alert.severity == "critical"

    def test_no_duplicate_while_firing(self, db_session):
        svc = SloAlertService(db_session)
        svc.evaluate("negmarket_api", "burning", 30.0)
        again = svc.evaluate("negmarket_api", "burning", 25.0)
        assert again is not None
        firing = (
            db_session.query(SloAlertModel)
            .filter(SloAlertModel.slo_name == "negmarket_api", SloAlertModel.status == "firing")
            .all()
        )
        assert len(firing) == 1
        assert firing[0].remaining_pct == 25.0  # 更新最新值但不重复告警

    def test_healthy_no_alert(self, db_session):
        alert = SloAlertService(db_session).evaluate("negmarket_api", "healthy", 90.0)
        assert alert is None

    def test_resolve_on_recovery(self, db_session):
        svc = SloAlertService(db_session)
        svc.evaluate("negmarket_api", "exhausted", 0.0)
        resolved = svc.evaluate("negmarket_api", "healthy", 95.0)
        assert resolved is not None
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None

    def test_get_status_shows_active(self, db_session):
        svc = SloAlertService(db_session)
        svc.evaluate("negmarket_api", "burning", 20.0)
        status = svc.get_status()
        assert "negmarket_api" in status
        assert status["negmarket_api"]["status"] == "firing"

    def test_get_status_empty_when_no_alert(self, db_session):
        assert SloAlertService(db_session).get_status() == {}

    def test_list_events_history(self, db_session):
        svc = SloAlertService(db_session)
        svc.evaluate("negmarket_api", "burning", 20.0)
        svc.evaluate("negmarket_api", "healthy", 90.0)
        events = svc.list_events(slo_name="negmarket_api")
        assert len(events) >= 2
        assert {e["status"] for e in events} >= {"firing", "resolved"}


class TestSloAlertWebhook:
    def test_webhook_sent_on_trigger(self, db_session, monkeypatch):
        sent = []

        class FakeResp:
            status = 200

        import urllib.request

        def fake_urlopen(req, timeout):
            sent.append((req.full_url, req.data))
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://localhost:9999/alert")
        SloAlertService(db_session).evaluate("negmarket_api", "burning", 20.0)
        assert len(sent) == 1
        assert sent[0][0] == "http://localhost:9999/alert"

    def test_webhook_sent_on_resolve(self, db_session, monkeypatch):
        sent = []

        class FakeResp:
            status = 200

        import urllib.request

        def fake_urlopen(req, timeout):
            sent.append(req.full_url)
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://localhost:9999/alert")
        svc = SloAlertService(db_session)
        svc.evaluate("negmarket_api", "burning", 20.0)
        assert len(sent) == 1
        svc.evaluate("negmarket_api", "healthy", 90.0)
        assert len(sent) == 2

    def test_no_url_records_only(self, db_session):
        SloAlertService(db_session).evaluate("negmarket_api", "burning", 20.0)
        firing = (
            db_session.query(SloAlertModel)
            .filter(SloAlertModel.slo_name == "negmarket_api", SloAlertModel.status == "firing")
            .count()
        )
        assert firing == 1

    def test_webhook_failure_does_not_raise(self, db_session, monkeypatch):
        import urllib.request

        def boom(req, timeout):
            raise RuntimeError("network down")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://localhost:9999/alert")
        alert = SloAlertService(db_session).evaluate("negmarket_api", "burning", 20.0)
        assert alert is not None


class TestSloAlertApi:
    def test_alerts_status_endpoint(self, client):
        get_slo_manager().record_availability("negmarket_api", False)  # 制造一次失败
        r = client.get("/monitoring/alerts/status")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_alerts_events_endpoint(self, client):
        get_slo_manager().record_availability("negmarket_api", False)
        client.get("/monitoring/alerts/status")
        r = client.get("/monitoring/alerts/events?slo_name=negmarket_api")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
