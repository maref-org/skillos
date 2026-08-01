"""SLO 告警服务 — 错误预算恶化的主动通知（M11）

状态机（按 slo_name 维度）::

    none ──burning/exhausted──▶ firing ──healthy/at_risk──▶ resolved

去重：同一 slo 在 firing 中不重复触发；仅在 none→firing（触发）与
firing→resolved（恢复）两个沿发送出站 webhook 通知。

出站通道：HTTP POST 到 `SKILLOS_SLO_ALERT_WEBHOOK_URL`（环境变量）。
无 URL 配置时仅落库（slo_alerts 表），不实际发送 → 无 key/无配置环境可测。

用法::

    SloAlertService(db).evaluate(slo_name, status, remaining_pct)  # 状态机判定
    SloAlertService(db).get_status()                                # 当前告警状态
    SloAlertService(db).list_events()                               # 事件历史
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.models import SloAlertModel

logger = logging.getLogger(__name__)

_ALERTING_STATUSES = ("burning", "exhausted")
_SEVERITY_MAP = {"burning": "warning", "exhausted": "critical"}


class SloAlertService:
    """SLO 告警状态机 + 事件落库 + 出站 webhook。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def evaluate(self, slo_name: str, status: str, remaining_pct: float) -> SloAlertModel | None:
        """按快照状态推进告警状态机。返回新增/更新的事件记录，无变化返回 None。"""
        active = (
            self._db.query(SloAlertModel)
            .filter(SloAlertModel.slo_name == slo_name, SloAlertModel.resolved_at.is_(None))
            .order_by(SloAlertModel.started_at.desc())
            .first()
        )
        now = datetime.now(timezone.utc)

        if status in _ALERTING_STATUSES:
            if active is not None:
                # 已在告警中，更新最新 remaining_pct，不重复触发
                active.remaining_pct = remaining_pct
                self._db.flush()
                return active
            alert = SloAlertModel(
                slo_name=slo_name,
                status="firing",
                severity=_SEVERITY_MAP.get(status, "warning"),
                remaining_pct=remaining_pct,
                started_at=now,
                payload={"triggered_status": status, "remaining_pct": remaining_pct},
            )
            self._db.add(alert)
            self._db.flush()
            self._dispatch("firing", slo_name, status, remaining_pct)
            return alert

        if active is not None:
            # 恢复：保留 firing 记录的触发历史（仅标记 resolved_at），另插 resolved 事件
            active.resolved_at = now
            active.payload = {**(active.payload or {}), "resolved_status": status}
            resolved = SloAlertModel(
                slo_name=slo_name,
                status="resolved",
                severity="info",
                remaining_pct=remaining_pct,
                started_at=now,
                resolved_at=now,
                payload={"triggered_status": active.payload.get("triggered_status"), "resolved_status": status},
            )
            self._db.add(resolved)
            self._db.flush()
            self._dispatch("resolved", slo_name, status, remaining_pct)
            return resolved
        return None

    def get_status(self) -> dict[str, Any]:
        """返回各 SLO 当前告警状态（活跃未恢复的 firing 记录）。"""
        rows = (
            self._db.query(SloAlertModel)
            .filter(SloAlertModel.resolved_at.is_(None))
            .order_by(SloAlertModel.started_at.desc())
            .all()
        )
        status: dict[str, Any] = {}
        for r in rows:
            status.setdefault(
                r.slo_name,
                {
                    "status": r.status,
                    "severity": r.severity,
                    "remaining_pct": r.remaining_pct,
                    "started_at": _iso(r.started_at),
                },
            )
        return status

    def list_events(self, slo_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """返回告警事件历史（按时间倒序）。"""
        q = self._db.query(SloAlertModel)
        if slo_name:
            q = q.filter(SloAlertModel.slo_name == slo_name)
        rows = q.order_by(SloAlertModel.started_at.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "slo_name": r.slo_name,
                "status": r.status,
                "severity": r.severity,
                "remaining_pct": r.remaining_pct,
                "started_at": _iso(r.started_at),
                "resolved_at": _iso(r.resolved_at),
                "payload": r.payload or {},
            }
            for r in rows
        ]

    def _dispatch(self, event: str, slo_name: str, status: str, remaining_pct: float) -> None:
        """出站 webhook 通知。无 URL 或发送失败仅记日志，不影响主流程。"""
        url = os.getenv("SKILLOS_SLO_ALERT_WEBHOOK_URL", "").strip()
        if not url:
            logger.info("SLO alert %s for %s (no webhook URL, recorded only)", event, slo_name)
            return
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            logger.warning("SLO alert webhook URL rejected (scheme must be http/https): %s", parsed.scheme)
            return
        payload = json.dumps(
            {
                "event": event,
                "slo_name": slo_name,
                "status": status,
                "remaining_pct": remaining_pct,
                "timestamp": _iso(datetime.now(timezone.utc)),
            }
        ).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            # urlopen 受 scheme 白名单约束（仅 http/https），URL 来自环境变量
            with urllib.request.urlopen(req, timeout=5) as resp:  # nosec B310
                logger.info("SLO alert webhook sent: %s -> %s (%s)", event, slo_name, resp.status)
        except Exception as exc:  # noqa: BLE001 出站失败不影响主流程
            logger.warning("SLO alert webhook failed for %s: %s", slo_name, exc)


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None
