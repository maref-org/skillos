"""Tests for M12-P1 — 告警多渠道推送

覆盖：渠道工厂降级、webhook 保留、smtp/dingtalk/wecom 无 key 降级、
dingtalk/wecom payload 构造（monkeypatch urllib）、_dispatch 走渠道。
"""

import pytest

pytest.importorskip("fastapi")

from skillos.observability.alert_channels import (
    AlertEvent,
    NotConfiguredError,
    SmtpChannel,
    WebhookChannel,
    get_channels,
)
from skillos.observability.slo_alerts import SloAlertService


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "SKILLOS_ALERT_CHANNELS",
        "SKILLOS_SLO_ALERT_WEBHOOK_URL",
        "SKILLOS_SMTP_HOST",
        "SKILLOS_SMTP_USER",
        "SKILLOS_SMTP_PASS",
        "SKILLOS_SMTP_FROM",
        "SKILLOS_SMTP_TO",
        "SKILLOS_DINGTALK_WEBHOOK_URL",
        "SKILLOS_WECOM_WEBHOOK_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


class TestChannelFactory:
    def test_default_is_webhook_when_unset(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://hooks.local/h")
        channels = get_channels()
        assert len(channels) == 1
        assert channels[0].name == "webhook"

    def test_webhook_missing_url_yields_none(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_ALERT_CHANNELS", "webhook")
        assert get_channels() == []

    def test_smtp_missing_config_skipped(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_ALERT_CHANNELS", "webhook,smtp,dingtalk,wecom")
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://hooks.local/h")
        channels = get_channels()
        names = [c.name for c in channels]
        assert names == ["webhook"]

    def test_all_channels_configured(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_ALERT_CHANNELS", "webhook,smtp,dingtalk,wecom")
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://hooks.local/h")
        monkeypatch.setenv("SKILLOS_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SKILLOS_SMTP_USER", "u")
        monkeypatch.setenv("SKILLOS_SMTP_PASS", "p")
        monkeypatch.setenv("SKILLOS_SMTP_FROM", "a@b.c")
        monkeypatch.setenv("SKILLOS_SMTP_TO", "x@y.z")
        monkeypatch.setenv("SKILLOS_DINGTALK_WEBHOOK_URL", "http://dingtalk/h")
        monkeypatch.setenv("SKILLOS_WECOM_WEBHOOK_URL", "http://wecom/h")
        channels = get_channels()
        assert [c.name for c in channels] == ["webhook", "smtp", "dingtalk", "wecom"]

    def test_unknown_channel_ignored(self, monkeypatch):
        monkeypatch.setenv("SKILLOS_ALERT_CHANNELS", "webhook,foo")
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://hooks.local/h")
        assert [c.name for c in get_channels()] == ["webhook"]

    def test_smtp_missing_config_raises(self):
        with pytest.raises(NotConfiguredError):
            SmtpChannel()


class TestChannelPayloads:
    def test_webhook_posts_json(self, monkeypatch):
        sent = {}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=5):
            sent["url"] = req.full_url
            sent["body"] = req.data.decode()
            sent["headers"] = req.headers
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        channel = WebhookChannel("http://hooks.local/h")
        event = AlertEvent(
            event="firing", slo_name="api", status="burning",
            remaining_pct=30.0, timestamp="2026-08-01T00:00:00Z",
        )
        assert channel.send(event) is True
        assert sent["url"] == "http://hooks.local/h"
        assert any(k.lower() == "content-type" and v == "application/json" for k, v in sent["headers"].items())
        assert '"slo_name": "api"' in sent["body"]

    def test_webhook_rejects_non_http_scheme(self):
        channel = WebhookChannel("file:///etc/passwd")
        assert channel.send(AlertEvent("firing", "api", "burning", 30.0, "ts")) is False

    def test_dingtalk_payload_format(self, monkeypatch):
        captured = {}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=5):
            import json

            captured["payload"] = json.loads(req.data.decode())
            return FakeResp()

        import skillos.observability.alert_channels as ac

        monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)
        channel = ac.DingtalkChannel("http://dingtalk/h")
        event = AlertEvent("firing", "api", "burning", 30.0, "ts")
        assert channel.send(event) is True
        assert captured["payload"]["msgtype"] == "text"
        assert "api" in captured["payload"]["text"]["content"]

    def test_wecom_payload_format(self, monkeypatch):
        captured = {}

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=5):
            import json

            captured["payload"] = json.loads(req.data.decode())
            return FakeResp()

        import skillos.observability.alert_channels as ac

        monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)
        channel = ac.WecomChannel("http://wecom/h")
        event = AlertEvent("firing", "api", "burning", 30.0, "ts")
        assert channel.send(event) is True
        assert captured["payload"]["msgtype"] == "text"
        assert "api" in captured["payload"]["text"]["content"]


class TestDispatchUsesChannels:
    def test_dispatch_no_channel_recorded_only(self, db_session, monkeypatch):
        monkeypatch.delenv("SKILLOS_ALERT_CHANNELS", raising=False)
        monkeypatch.delenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", raising=False)
        alert = SloAlertService(db_session).evaluate("api", "burning", 30.0)
        assert alert is not None
        assert alert.status == "firing"

    def test_dispatch_sends_to_webhook_channel(self, db_session, monkeypatch):
        monkeypatch.setenv("SKILLOS_ALERT_CHANNELS", "webhook")
        monkeypatch.setenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "http://hooks.local/h")
        sent = []

        class FakeResp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(req, timeout=5):
            sent.append(req.data.decode())
            return FakeResp()

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        alert = SloAlertService(db_session).evaluate("api", "burning", 30.0)
        assert alert is not None
        assert len(sent) == 1
        assert '"event": "firing"' in sent[0]
