"""
Content Calendar — cross-platform scheduling with conflict detection.

SKILL.md spec reference:
  - Same platform: min 2hr interval
  - Cross-platform stagger: 5min intervals
  - Status: draft → scheduled → published → failed
"""
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EntryStatus(Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CalendarEntry:
    id: str
    content_type: str  # announcement / tutorial / story / milestone / video / general
    source_content_id: str
    title: str = ""
    platform_variants: dict[str, dict] = field(default_factory=dict)
    scheduled_at: dict[str, str] = field(default_factory=dict)  # platform → ISO timestamp
    status: str = "draft"
    published_ids: dict[str, str] = field(default_factory=dict)  # platform → post_id
    metrics: dict[str, dict] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "content_type": self.content_type,
            "source_content_id": self.source_content_id, "title": self.title,
            "platform_variants": self.platform_variants,
            "scheduled_at": self.scheduled_at, "status": self.status,
            "published_ids": self.published_ids, "metrics": self.metrics,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CalendarEntry":
        return cls(
            id=d["id"], content_type=d.get("content_type", "general"),
            source_content_id=d.get("source_content_id", ""),
            title=d.get("title", ""),
            platform_variants=d.get("platform_variants", {}),
            scheduled_at=d.get("scheduled_at", {}),
            status=d.get("status", "draft"),
            published_ids=d.get("published_ids", {}),
            metrics=d.get("metrics", {}),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


# Platform priority (lower = publish first)
PLATFORM_PRIORITY = [
    "github", "twitter", "linkedin", "discord",
    "youtube", "bilibili", "threads", "instagram",
    "xiaohongshu", "douyin", "tiktok", "weibo", "jike",
]

# Optimal posting windows (UTC, 24hr weekdays)
PLATFORM_WINDOWS = {
    "twitter": {"days": [2, 3, 4, 5], "hours": (15, 18), "max_per_day": 5},
    "linkedin": {"days": [1, 2, 3, 4], "hours": (8, 10), "max_per_day": 2},
    "github": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (15, 20), "max_per_day": 3},
    "youtube": {"days": [5, 6], "hours": (12, 16), "max_per_day": 1},
    "bilibili": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (12, 14), "max_per_day": 2},
    "xiaohongshu": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (7, 9), "max_per_day": 3},
    "douyin": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (18, 21), "max_per_day": 3},
    "instagram": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (11, 13), "max_per_day": 2},
    "discord": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (10, 22), "max_per_day": 10},
    "threads": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (12, 15), "max_per_day": 3},
    "weibo": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (8, 10), "max_per_day": 5},
    "tiktok": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (12, 14), "max_per_day": 3},
    "jike": {"days": [0, 1, 2, 3, 4, 5, 6], "hours": (10, 18), "max_per_day": 3},
}


class ContentCalendar:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get(
            "SKILLOS_DB_PATH",
            os.path.expanduser("~/.skillos/data/content_calendar.db"),
        )
        self._entries: dict[str, CalendarEntry] = {}
        self._db = None

    def _get_db(self):
        if self._db is None:
            try:
                from .db import CalendarDB
            except ImportError:
                from db import CalendarDB  # fallback for direct execution
            self._db = CalendarDB(self.db_path)
            self._db.init()
        return self._db

    def schedule(self,
                content_type: str,
                source_content_id: str,
                platforms: list[str],
                base_time: str,
                title: str = "",
                **kwargs) -> CalendarEntry:
        """Schedule content across platforms with auto-staggered times."""
        entry_id = str(uuid.uuid4())[:12]

        # Generate staggered times
        base_dt = datetime.fromisoformat(base_time)
        scheduled_at = {}
        for i, platform in enumerate(platforms):
            # Stagger by 5 minutes, adjust to platform optimal window
            platform_dt = base_dt + timedelta(minutes=i * 5)
            scheduled_at[platform] = platform_dt.isoformat()

        entry = CalendarEntry(
            id=entry_id,
            content_type=content_type,
            source_content_id=source_content_id,
            title=title,
            scheduled_at=scheduled_at,
            status="scheduled",
            platform_variants={p: {} for p in platforms},
        )

        # Check conflicts
        conflicts = self._detect_conflicts(entry, scheduled_at)
        if conflicts:
            logger.warning(f"Schedule conflicts detected: {conflicts}")

        self._entries[entry_id] = entry

        # Persist
        try:
            self._get_db().upsert(entry)
        except Exception:
            logger.exception("Failed to persist calendar entry")

        return entry

    def _detect_conflicts(self, entry: CalendarEntry,
                        scheduled: dict[str, str]) -> list[str]:
        conflicts = []
        for platform, iso_ts in scheduled.items():
            target_dt = datetime.fromisoformat(iso_ts)
            for existing in self._entries.values():
                if existing.id == entry.id:
                    continue
                if platform in existing.scheduled_at:
                    existing_dt = datetime.fromisoformat(existing.scheduled_at[platform])
                    diff = abs((target_dt - existing_dt).total_seconds())
                    if diff < 7200:  # 2-hour minimum
                        conflicts.append(
                            f"{platform}: {iso_ts} conflicts with {existing.id} "
                            f"({existing.scheduled_at[platform]}, diff={diff/60:.0f}min)"
                        )
        return conflicts

    def get_entry(self, entry_id: str) -> CalendarEntry | None:
        return self._entries.get(entry_id)

    def update_status(self, entry_id: str, status: str,
                     published_ids: dict[str, str] | None = None):
        entry = self._entries.get(entry_id)
        if not entry:
            return
        entry.status = status
        entry.updated_at = datetime.now(UTC).isoformat()
        if published_ids:
            entry.published_ids.update(published_ids)
        try:
            self._get_db().upsert(entry)
        except Exception:
            pass

    def get_upcoming(self, platform: str | None = None,
                    limit: int = 20) -> list[CalendarEntry]:
        upcoming = []
        for e in self._entries.values():
            if e.status not in ("scheduled", "draft"):
                continue
            if platform:
                if platform not in e.scheduled_at:
                    continue
            upcoming.append(e)
        upcoming.sort(key=lambda e: min(e.scheduled_at.values()) if e.scheduled_at else "9999")
        return upcoming[:limit]

    def get_by_date(self, date_str: str) -> list[CalendarEntry]:
        results = []
        for e in self._entries.values():
            for iso_ts in e.scheduled_at.values():
                if iso_ts.startswith(date_str):
                    results.append(e)
                    break
        return results

    def suggest_time(self, platform: str, after: str | None = None
                    ) -> str | None:
        """Suggest an optimal publishing time for a platform."""
        window = PLATFORM_WINDOWS.get(platform, {})
        if not window:
            return None

        now = datetime.fromisoformat(after) if after else datetime.now(UTC)

        # Find the next available window
        target_hours = window.get("hours", (12, 16))
        target_days = window.get("days", list(range(7)))

        for offset in range(14):  # look ahead 14 days
            candidate = now + timedelta(days=offset)
            candidate_day = candidate.weekday()
            if candidate_day not in target_days:
                continue

            suggested = datetime(
                candidate.year, candidate.month, candidate.day,
                target_hours[0], 0, 0, tzinfo=UTC
            )

            # Check no conflict within 2hr window
            has_conflict = False
            for e in self._entries.values():
                if platform not in e.scheduled_at:
                    continue
                existing_dt = datetime.fromisoformat(e.scheduled_at[platform])
                diff = abs((suggested - existing_dt).total_seconds())
                if diff < 7200:
                    has_conflict = True
                    break

            if not has_conflict:
                return suggested.isoformat()

        return None
