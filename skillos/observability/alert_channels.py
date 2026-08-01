"""告警渠道 — 多渠道推送抽象（M12-P1）

与 M6 支付抽象层同构：`AlertChannel` 协议 + 适配器 + `get_channel()` 工厂。
无渠道 key 时降级（不抛错，仅日志），有 key 时走真实通道。

渠道列表通过 `SKILLOS_ALERT_CHANNELS` 环境变量配置（逗号分隔，如 "webhook,smtp"）。
未配置时默认 ["webhook"]（保持 M11 行为）。

渠道适配器:
  - webhook:  通用 HTTP POST（M11 原有行为，scheme 白名单 http/https）
  - smtp:     SMTP 邮件（SKILLOS_SMTP_HOST/PORT/USER/PASS/FROM/TO）
  - dingtalk: 钉钉机器人 webhook（SKILLOS_DINGTALK_WEBHOOK_URL）
  - wecom:    企业微信机器人 webhook（SKILLOS_WECOM_WEBHOOK_URL）
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger(__name__)


class NotConfiguredError(Exception):
    """渠道缺少必要配置时抛出（工厂捕获并跳过）。"""


@dataclass
class AlertEvent:
    """告警事件载荷。"""

    event: str  # firing / resolved
    slo_name: str
    status: str
    remaining_pct: float
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "event": self.event,
            "slo_name": self.slo_name,
            "status": self.status,
            "remaining_pct": self.remaining_pct,
            "timestamp": self.timestamp,
        }


class AlertChannel(Protocol):
    """告警通道协议：send 返回是否成功。"""

    name: str

    def send(self, event: AlertEvent) -> bool: ...


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone(timezone.utc).isoformat()


def _http_post(url: str, payload: dict) -> bool:
    """POST JSON 到 URL（scheme 白名单 http/https）。返回是否成功。"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.warning("Channel URL rejected (scheme must be http/https): %s", parsed.scheme)
        return False
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        # nosec B310 - URL 来自配置且 scheme 白名单（http/https）
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
            return 200 <= resp.status < 300
    except Exception as exc:  # noqa: BLE001 渠道失败不影响主流程
        logger.warning("Channel HTTP POST failed for %s: %s", url, exc)
        return False


class WebhookChannel:
    """通用 HTTP webhook（M11 原有行为）。"""

    name = "webhook"

    def __init__(self, url: str):
        self._url = url

    def send(self, event: AlertEvent) -> bool:
        return _http_post(self._url, event.to_dict())


class SmtpChannel:
    """SMTP 邮件通道。配置：SKILLOS_SMTP_HOST/PORT/USER/PASS/FROM/TO（TO 逗号分隔）。"""

    name = "smtp"

    REQUIRED_ENV = (
        "SKILLOS_SMTP_HOST",
        "SKILLOS_SMTP_USER",
        "SKILLOS_SMTP_PASS",
        "SKILLOS_SMTP_FROM",
        "SKILLOS_SMTP_TO",
    )

    def __init__(self):
        missing = [k for k in self.REQUIRED_ENV if not os.getenv(k, "").strip()]
        if missing:
            raise NotConfiguredError(f"SMTP missing config: {', '.join(missing)}")
        self._host = os.getenv("SKILLOS_SMTP_HOST", "")
        self._port = int(os.getenv("SKILLOS_SMTP_PORT", "465"))
        self._user = os.getenv("SKILLOS_SMTP_USER", "")
        self._pass = os.getenv("SKILLOS_SMTP_PASS", "")
        self._from = os.getenv("SKILLOS_SMTP_FROM", "")
        self._to = [t.strip() for t in os.getenv("SKILLOS_SMTP_TO", "").split(",") if t.strip()]

    def send(self, event: AlertEvent) -> bool:
        subject = f"[SkillOS SLO {event.event}] {event.slo_name} - {event.status}"
        body = json.dumps(event.to_dict(), ensure_ascii=False, indent=2)
        message = f"Subject: {subject}\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\n{body}"
        try:
            with smtplib.SMTP_SSL(self._host, self._port, timeout=10) as server:
                server.login(self._user, self._pass)
                server.sendmail(self._from, self._to, message.encode("utf-8"))
            return True
        except Exception as exc:  # noqa: BLE001 渠道失败不影响主流程
            logger.warning("SMTP send failed for %s: %s", event.slo_name, exc)
            return False


class DingtalkChannel:
    """钉钉机器人 webhook。配置：SKILLOS_DINGTALK_WEBHOOK_URL。"""

    name = "dingtalk"

    def __init__(self, url: str):
        if not url:
            raise NotConfiguredError("dingtalk missing SKILLOS_DINGTALK_WEBHOOK_URL")
        self._url = url

    def send(self, event: AlertEvent) -> bool:
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"[SkillOS SLO {event.event}] {event.slo_name} {event.status} ({event.remaining_pct}%)"
            },
        }
        return _http_post(self._url, payload)


class WecomChannel:
    """企业微信机器人 webhook。配置：SKILLOS_WECOM_WEBHOOK_URL。"""

    name = "wecom"

    def __init__(self, url: str):
        if not url:
            raise NotConfiguredError("wecom missing SKILLOS_WECOM_WEBHOOK_URL")
        self._url = url

    def send(self, event: AlertEvent) -> bool:
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"[SkillOS SLO {event.event}] {event.slo_name} {event.status} ({event.remaining_pct}%)"
            },
        }
        return _http_post(self._url, payload)


def _build_channel(name: str) -> AlertChannel | None:
    """按名实例化单个渠道；配置缺失或未知名返回 None。"""
    name = name.strip().lower()
    if name == "webhook":
        url = os.getenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "").strip()
        return WebhookChannel(url) if url else None
    if name == "smtp":
        return SmtpChannel()  # 构造时校验，缺配置抛 NotConfiguredError
    if name == "dingtalk":
        return DingtalkChannel(os.getenv("SKILLOS_DINGTALK_WEBHOOK_URL", "").strip())
    if name == "wecom":
        return WecomChannel(os.getenv("SKILLOS_WECOM_WEBHOOK_URL", "").strip())
    logger.warning("Unknown alert channel: %s", name)
    return None


def get_channels() -> list[AlertChannel]:
    """返回可用告警通道列表（配置缺失的渠道跳过）。未配置时默认 [webhook]。"""
    raw = os.getenv("SKILLOS_ALERT_CHANNELS", "").strip()
    names = [n for n in raw.split(",") if n.strip()] if raw else ["webhook"]
    channels: list[AlertChannel] = []
    for name in names:
        try:
            ch = _build_channel(name)
            if ch is not None:
                channels.append(ch)
        except NotConfiguredError as exc:
            logger.info("Alert channel %s skipped: %s", name, exc)
    return channels
