"""SLO 告警服务 — 错误预算恶化的主动通知（M11/M12）

状态机（按 slo_name 维度）::

    none ──burning/exhausted──▶ firing ──healthy/at_risk──▶ resolved

去重：同一 slo 在 firing 中不重复触发；仅在 none→firing（触发）与
firing→resolved（恢复）两个沿发送多渠道通知（webhook/smtp/dingtalk/wecom，
见 alert_channels）。无可用渠道时仅落库（slo_alerts 表）→ 无 key/无配置环境可测。

用法::

    SloAlertService(db).evaluate(slo_name, status, remaining_pct)  # 状态机判定
    SloAlertService(db).get_status()                                # 当前告警状态
    SloAlertService(db).list_events()                               # 事件历史
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.models import MaintenanceWindowModel, SloAlertModel

logger = logging.getLogger(__name__)

_ALERTING_STATUSES = ("burning", "exhausted")
_SEVERITY_MAP = {"burning": "warning", "exhausted": "critical"}


def _window_covers(now: datetime, cron_expr: str, duration_minutes: int) -> bool:
    """判定 now 是否落在 cron 周期窗口内（窗口为 [最近一次 cron 触发, +duration)）。

    cron 触发的窗口若已过期（本次触发早于 now），则找上一次触发作为窗口起点。
    """
    try:
        from croniter import croniter  # type: ignore[import-untyped]

        cron = croniter(cron_expr, now)
        # 上次触发时刻（get_prev）与下次触发时刻
        prev = cron.get_prev(datetime)
        return (now - prev).total_seconds() < duration_minutes * 60
    except Exception:  # noqa: BLE001 无效 cron 视为不覆盖
        return False


class SloAlertService:
    """SLO 告警状态机 + 事件落库 + 出站 webhook。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def evaluate(self, slo_name: str, status: str, remaining_pct: float) -> SloAlertModel | None:
        """按快照状态推进告警状态机。返回新增/更新的事件记录，无变化返回 None。

        静默（M12-P3）：静默截止前，该 SLO 的告警不触发、不置 resolved（视为已抑制）。
        """
        now = datetime.now(timezone.utc)
        if self.is_silenced(slo_name, now=now):
            return None
        if self.in_maintenance_window(slo_name, now=now):
            return None

        active = (
            self._db.query(SloAlertModel)
            .filter(
                SloAlertModel.slo_name == slo_name,
                SloAlertModel.resolved_at.is_(None),
                SloAlertModel.status != "silenced",
            )
            .order_by(SloAlertModel.started_at.desc())
            .first()
        )

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
        """返回各 SLO 当前告警状态（活跃未恢复的 firing 记录，静默记录不计）。"""
        rows = (
            self._db.query(SloAlertModel)
            .filter(SloAlertModel.resolved_at.is_(None), SloAlertModel.status != "silenced")
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

    def silence(self, slo_name: str, until: datetime) -> SloAlertModel:
        """设置该 SLO 的告警静默截止时间。静默期内 evaluate 不触发。"""
        active = (
            self._db.query(SloAlertModel)
            .filter(SloAlertModel.slo_name == slo_name, SloAlertModel.resolved_at.is_(None))
            .order_by(SloAlertModel.started_at.desc())
            .first()
        )
        if active is None:
            active = SloAlertModel(
                slo_name=slo_name,
                status="silenced",
                severity="info",
                remaining_pct=0.0,
                started_at=datetime.now(timezone.utc).replace(tzinfo=None),
                payload={"silenced_until": _iso(until)},
            )
            self._db.add(active)
        active.silenced_until = until.replace(tzinfo=None)
        active.payload = {**(active.payload or {}), "silenced_until": _iso(until)}
        self._db.flush()
        return active

    def unsilence(self, slo_name: str) -> bool:
        """解除该 SLO 的静默。返回是否确有静默被解除。"""
        rows = (
            self._db.query(SloAlertModel)
            .filter(
                SloAlertModel.slo_name == slo_name,
                SloAlertModel.resolved_at.is_(None),
                SloAlertModel.silenced_until.isnot(None),
            )
            .all()
        )
        if not rows:
            return False
        for r in rows:
            r.silenced_until = None
            if r.status == "silenced":
                r.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self._db.flush()
        return True

    def is_silenced(self, slo_name: str, now: datetime | None = None) -> bool:
        """该 SLO 当前是否处于静默期。"""
        if now is None:
            # DB DateTime 读回为 naive UTC，比较用 naive now
            now = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            now = now.replace(tzinfo=None)
        row = (
            self._db.query(SloAlertModel)
            .filter(
                SloAlertModel.slo_name == slo_name,
                SloAlertModel.resolved_at.is_(None),
                SloAlertModel.silenced_until.isnot(None),
            )
            .order_by(SloAlertModel.silenced_until.desc())
            .first()
        )
        return row is not None and row.silenced_until is not None and row.silenced_until > now

    def list_silences(self) -> list[dict[str, Any]]:
        """返回当前生效的静默（silenced_until 未过期且未解除）。"""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = (
            self._db.query(SloAlertModel)
            .filter(
                SloAlertModel.resolved_at.is_(None),
                SloAlertModel.silenced_until.isnot(None),
                SloAlertModel.silenced_until > now,
            )
            .all()
        )
        return [
            {
                "slo_name": r.slo_name,
                "until": _iso(r.silenced_until),
                "started_at": _iso(r.started_at),
            }
            for r in rows
        ]

    def in_maintenance_window(self, slo_name: str, now: datetime | None = None) -> bool:
        """该 SLO 当前是否处于周期维护窗口内（M13-P2）。"""
        if now is None:
            now = datetime.now(timezone.utc)
        rows = self._db.query(MaintenanceWindowModel).filter(MaintenanceWindowModel.enabled.is_(True)).all()
        for w in rows:
            if w.slo_name != "*" and w.slo_name != slo_name:
                continue
            if _window_covers(now, w.cron_expression, w.duration_minutes):
                return True
        return False

    def create_maintenance_window(
        self,
        cron_expression: str,
        duration_minutes: int = 60,
        slo_name: str = "*",
        description: str = "",
    ) -> MaintenanceWindowModel:
        """创建周期维护窗口。cron 无效时抛 ValueError。"""
        if duration_minutes <= 0:
            raise ValueError(f"duration_minutes must be positive: {duration_minutes}")
        from croniter import croniter  # type: ignore[import-untyped]

        try:
            croniter(cron_expression, datetime.now())
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Invalid cron expression: {cron_expression}") from exc
        window = MaintenanceWindowModel(
            slo_name=slo_name,
            cron_expression=cron_expression,
            duration_minutes=duration_minutes,
            enabled=True,
            description=description,
        )
        self._db.add(window)
        self._db.flush()
        return window

    def list_maintenance_windows(self) -> list[dict[str, Any]]:
        """返回全部维护窗口配置（含禁用）。"""
        rows = self._db.query(MaintenanceWindowModel).order_by(MaintenanceWindowModel.created_at.asc()).all()
        return [
            {
                "id": w.id,
                "slo_name": w.slo_name,
                "cron_expression": w.cron_expression,
                "duration_minutes": w.duration_minutes,
                "enabled": w.enabled,
                "description": w.description,
                "created_at": _iso(w.created_at),
            }
            for w in rows
        ]

    def delete_maintenance_window(self, window_id: str) -> bool:
        """删除维护窗口。返回是否确有删除。"""
        row = self._db.query(MaintenanceWindowModel).filter(MaintenanceWindowModel.id == window_id).first()
        if row is None:
            return False
        self._db.delete(row)
        self._db.flush()
        return True

    def _dispatch(self, event: str, slo_name: str, status: str, remaining_pct: float) -> None:
        """出站多渠道通知（M12-P1）。无可用渠道仅记日志，不影响主流程。"""
        from skillos.observability.alert_channels import AlertEvent, get_channels

        channels = get_channels()
        if not channels:
            logger.info("SLO alert %s for %s (no channel available, recorded only)", event, slo_name)
            return
        alert_event = AlertEvent(
            event=event,
            slo_name=slo_name,
            status=status,
            remaining_pct=remaining_pct,
            timestamp=_iso(datetime.now(timezone.utc)) or "",
        )
        for ch in channels:
            try:
                if ch.send(alert_event):
                    logger.info("SLO alert sent via %s: %s -> %s", ch.name, event, slo_name)
            except Exception as exc:  # noqa: BLE001 渠道失败不影响主流程
                logger.warning("SLO alert channel %s failed for %s: %s", ch.name, slo_name, exc)


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat() if dt else None
