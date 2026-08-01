"""SLO 快照服务 — 错误预算历史持久化 + 趋势查询（M10）

SLOManager 是内存单例，服务重启即丢历史。本服务在「端点被访问」时机把
每个 SLO 的错误预算状态（status + remaining_pct）落库到 slo_snapshots 表，
提供按日聚合的趋势查询，支撑运营面板的 SLO 趋势曲线。

用法::

    SloSnapshotService(db).capture()                       # 落一条快照（每个 SLO）
    SloSnapshotService(db).get_trend("negmarket_api", 7)   # 近 7 天按日趋势
    SloSnapshotService(db).get_trend(days=7)               # 全部 SLO 趋势
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from skillos.db.models import SloSnapshotModel
from skillos.kernel.slo import get_slo_manager

logger = logging.getLogger(__name__)


class SloSnapshotService:
    """SLO 快照落库 + 趋势查询。"""

    def __init__(self, db_session: Session):
        self._db = db_session

    def capture(self, slo_names: list[str] | None = None) -> int:
        """把当前 SLOManager 状态落一条快照（每个 SLO 一条）。返回写入条数。"""
        summary = get_slo_manager().get_slo_summary()
        names = slo_names or list(summary.keys())
        now = datetime.now(timezone.utc)
        count = 0
        for name in names:
            item = summary.get(name)
            if not isinstance(item, dict):
                continue
            eb = item.get("error_budget", {})
            self._db.add(
                SloSnapshotModel(
                    slo_name=name,
                    status=eb.get("status", "healthy"),
                    remaining_pct=eb.get("remaining_pct", 0.0) or 0.0,
                    sampled_at=now,
                )
            )
            count += 1
        if count:
            self._db.flush()
        return count

    def get_trend(
        self,
        slo_name: str | None = None,
        days: int = 7,
    ) -> dict[str, list[dict[str, Any]]] | list[dict[str, Any]]:
        """查询 SLO 历史趋势。

        按 `sampled_at` 按日聚合，取每日最后一条快照。
        slo_name 省略时返回全部 SLO：{slo_name: [ {date, remaining_pct, status}, ... ]}。
        slo_name 指定时直接返回该 SLO 的列表。
        """
        start = datetime.now(timezone.utc) - timedelta(days=days)
        q = self._db.query(SloSnapshotModel).filter(SloSnapshotModel.sampled_at >= start)
        if slo_name:
            q = q.filter(SloSnapshotModel.slo_name == slo_name)
        rows = q.order_by(SloSnapshotModel.sampled_at.asc()).all()

        if slo_name:
            return self._aggregate(rows)
        by_name: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_name.setdefault(row.slo_name, []).append(
                {"date": _day_key(row.sampled_at), "remaining_pct": row.remaining_pct, "status": row.status}
            )
        return {name: self._aggregate_list(items) for name, items in by_name.items()}

    def _aggregate(self, rows: list[SloSnapshotModel]) -> list[dict[str, Any]]:
        """按日聚合，每日取最后一条（sampled_at 最大）。"""
        latest_by_day: dict[str, dict[str, Any]] = {}
        for row in rows:
            day = _day_key(row.sampled_at)
            prev = latest_by_day.get(day)
            if prev is None or row.sampled_at >= prev["_t"]:
                latest_by_day[day] = {
                    "date": day,
                    "remaining_pct": row.remaining_pct,
                    "status": row.status,
                    "_t": row.sampled_at,
                }
        return [
            {"date": v["date"], "remaining_pct": v["remaining_pct"], "status": v["status"]}
            for v in latest_by_day.values()
        ]

    def _aggregate_list(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest_by_day: dict[str, dict[str, Any]] = {}
        for item in items:
            latest_by_day[item["date"]] = item  # 输入已按 sampled_at 升序，直接覆盖为当日末条
        return list(latest_by_day.values())


def _day_key(dt: datetime) -> str:
    """按 UTC 取日期键 YYYY-MM-DD。"""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
