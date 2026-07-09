"""In-memory Job Hunter activity feed for the local dashboard."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ActivityType = Literal["found", "filtered", "saved", "error", "cycle"]

_MAX_EVENTS = 300


@dataclass
class HunterStats:
    cycles_completed: int = 0
    found_total: int = 0
    filtered_total: int = 0
    saved_total: int = 0
    last_cycle_saved: int = 0
    last_cycle_at: str | None = None
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HunterState:
    """Thread-safe ring buffer of hunter events and counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
        self.stats = HunterStats()

    def record(
        self,
        event_type: ActivityType,
        *,
        job_title: str = "",
        company: str = "",
        platform: str = "",
        score: int | None = None,
        reason: str = "",
        job_id: int | None = None,
        message: str = "",
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "job_title": job_title,
            "company": company,
            "platform": platform,
            "score": score,
            "reason": reason,
            "job_id": job_id,
            "message": message,
        }
        with self._lock:
            self._events.appendleft(entry)
            if event_type == "found":
                self.stats.found_total += 1
            elif event_type == "filtered":
                self.stats.filtered_total += 1
            elif event_type == "saved":
                self.stats.saved_total += 1
            elif event_type == "cycle":
                self.stats.cycles_completed += 1
                self.stats.last_cycle_at = entry["ts"]
                self.stats.last_cycle_saved = int(message) if message.isdigit() else 0

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)[:limit]

    def get_stats_dict(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self.stats)


# Singleton used by job hunter + sync dashboard routes
hunter_state = HunterState()
