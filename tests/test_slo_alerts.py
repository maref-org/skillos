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


class TestSloAlertSilence:
    """M12-P3 — 告警静默策略（维护窗口）。"""

    def _silence(self, db_session, slo="negmarket_api", hours=2):
        from datetime import datetime, timedelta, timezone

        until = datetime.now(timezone.utc) + timedelta(hours=hours)
        SloAlertService(db_session).silence(slo, until)
        return until

    def test_silenced_not_triggered(self, db_session):
        self._silence(db_session)
        alert = SloAlertService(db_session).evaluate("negmarket_api", "burning", 10.0)
        assert alert is None
        assert SloAlertService(db_session).get_status() == {}

    def test_silence_expired_recovers(self, db_session):
        from datetime import datetime, timedelta, timezone

        until = datetime.now(timezone.utc) - timedelta(minutes=5)
        SloAlertService(db_session).silence("negmarket_api", until)
        assert SloAlertService(db_session).is_silenced("negmarket_api") is False
        alert = SloAlertService(db_session).evaluate("negmarket_api", "burning", 10.0)
        assert alert is not None
        assert alert.status == "firing"

    def test_unsilence(self, db_session):
        self._silence(db_session)
        assert SloAlertService(db_session).is_silenced("negmarket_api") is True
        assert SloAlertService(db_session).unsilence("negmarket_api") is True
        assert SloAlertService(db_session).is_silenced("negmarket_api") is False
        assert SloAlertService(db_session).unsilence("negmarket_api") is False

    def test_silence_only_affects_named_slo(self, db_session):
        self._silence(db_session, "negmarket_api")
        alert = SloAlertService(db_session).evaluate("other_slo", "burning", 10.0)
        assert alert is not None

    def test_list_silences(self, db_session):
        self._silence(db_session)
        silences = SloAlertService(db_session).list_silences()
        assert len(silences) == 1
        assert silences[0]["slo_name"] == "negmarket_api"

    def test_api_silence_flow(self, client):
        get_slo_manager().record_availability("negmarket_api", False)
        r = client.get("/monitoring/alerts/status")
        assert r.status_code == 200

        from datetime import datetime, timedelta, timezone

        until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        r = client.post("/monitoring/alerts/negmarket_api/silence", json={"until": until})
        assert r.status_code == 200
        assert r.json()["slo_name"] == "negmarket_api"

        r = client.get("/monitoring/alerts/silences")
        assert r.status_code == 200
        assert any(s["slo_name"] == "negmarket_api" for s in r.json())

        r = client.delete("/monitoring/alerts/negmarket_api/silence")
        assert r.status_code == 200
        assert r.json()["removed"] is True

    def test_api_silence_invalid_until(self, client):
        r = client.post("/monitoring/alerts/negmarket_api/silence", json={"until": "not-a-date"})
        assert r.status_code == 400 or r.status_code == 500


class TestMaintenanceWindow:
    """M13-P2 — SLO 维护窗口周期化。"""

    def test_window_covers_current(self, db_session):
        # 每分钟触发的 cron，now 恰在窗口内
        svc = SloAlertService(db_session)
        svc.create_maintenance_window("* * * * *", duration_minutes=1)
        alert = svc.evaluate("negmarket_api", "burning", 10.0)
        assert alert is None

    def test_window_does_not_cover(self, db_session):
        # 一年后才会触发的 cron → 现在不覆盖
        svc = SloAlertService(db_session)
        svc.create_maintenance_window("0 0 1 1 *", duration_minutes=1)  # 每年 1 月 1 日
        alert = svc.evaluate("negmarket_api", "burning", 10.0)
        assert alert is not None
        assert alert.status == "firing"

    def test_window_slo_name_scoped(self, db_session):
        svc = SloAlertService(db_session)
        svc.create_maintenance_window("* * * * *", duration_minutes=1, slo_name="other_slo")
        assert svc.evaluate("negmarket_api", "burning", 10.0) is not None
        assert svc.evaluate("other_slo", "burning", 10.0) is None

    def test_window_all_slos(self, db_session):
        svc = SloAlertService(db_session)
        svc.create_maintenance_window("* * * * *", duration_minutes=1, slo_name="*")
        assert svc.evaluate("negmarket_api", "burning", 10.0) is None

    def test_create_invalid_cron(self, db_session):
        with pytest.raises(ValueError, match="Invalid cron"):
            SloAlertService(db_session).create_maintenance_window("not-a-cron", 60)

    def test_create_invalid_duration(self, db_session):
        with pytest.raises(ValueError, match="positive"):
            SloAlertService(db_session).create_maintenance_window("* * * * *", 0)

    def test_delete_window(self, db_session):
        svc = SloAlertService(db_session)
        w = svc.create_maintenance_window("* * * * *", duration_minutes=1)
        assert svc.delete_maintenance_window(w.id) is True
        assert svc.delete_maintenance_window(w.id) is False

    def test_list_windows(self, db_session):
        svc = SloAlertService(db_session)
        svc.create_maintenance_window("* * * * *", duration_minutes=30, slo_name="api", description="周末维护")
        rows = svc.list_maintenance_windows()
        assert len(rows) == 1
        assert rows[0]["slo_name"] == "api"
        assert rows[0]["duration_minutes"] == 30

    def test_api_maintenance_crud(self, client):
        payload = {
            "cron_expression": "0 2 * * 6",
            "duration_minutes": 120,
            "slo_name": "*",
            "description": "每周六维护",
        }
        r = client.post("/monitoring/alerts/maintenance", json=payload)
        assert r.status_code == 200, r.text
        window_id = r.json()["window"]["id"]

        r = client.get("/monitoring/alerts/maintenance")
        assert r.status_code == 200
        assert any(w["id"] == window_id for w in r.json()["windows"])

        r = client.delete(f"/monitoring/alerts/maintenance/{window_id}")
        assert r.status_code == 200

        r = client.delete(f"/monitoring/alerts/maintenance/{window_id}")
        assert r.status_code == 404

    def test_api_maintenance_invalid_cron(self, client):
        r = client.post(
            "/monitoring/alerts/maintenance",
            json={"cron_expression": "bad-cron", "duration_minutes": 60},
        )
        assert r.status_code == 400


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
