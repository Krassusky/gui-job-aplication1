"""In-memory Job Hunter activity feed and run control for the local dashboard."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

ActivityType = Literal[
    "found", "filtered", "saved", "error", "cycle", "status", "thermal"
]

RunState = Literal["stopped", "running", "paused_thermal", "stopping"]

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
    run_state: RunState = "stopped"
    pause_reason: str = ""
    sensors: dict[str, Any] = field(default_factory=dict)


class HunterState:
    """Thread-safe ring buffer of hunter events, counters, and run control."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: deque[dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
        self.stats = HunterStats()
        self._want_running = False
        self._stop_cycle = threading.Event()
        self._hunt_thread: threading.Thread | None = None
        self._config_loader: Callable[[], Any] | None = None
        self._db = None

    def configure(self, *, config_loader: Callable[[], Any], db: Any) -> None:
        self._config_loader = config_loader
        self._db = db

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

    def set_run_state(self, state: RunState, reason: str = "", sensors: dict | None = None) -> None:
        with self._lock:
            self.stats.run_state = state
            self.stats.pause_reason = reason
            if sensors is not None:
                self.stats.sensors = sensors

    def update_sensors(self, sensors: dict) -> None:
        with self._lock:
            self.stats.sensors = sensors

    def want_running(self) -> bool:
        with self._lock:
            return self._want_running

    def cycle_should_stop(self) -> bool:
        return self._stop_cycle.is_set() or not self.want_running()

    def request_start(self) -> dict[str, Any]:
        """Start hunting (idempotent). Returns status payload."""
        with self._lock:
            if self._want_running and self._hunt_thread and self._hunt_thread.is_alive():
                return {"ok": True, "run_state": self.stats.run_state, "message": "already running"}
            if self._config_loader is None or self._db is None:
                return {"ok": False, "error": "Hunter not configured"}
            self._want_running = True
            self._stop_cycle.clear()
            self.stats.run_state = "running"
            self.stats.pause_reason = ""
            config_loader = self._config_loader
            db = self._db

        from worker.job_hunter import hunt_loop

        def _target() -> None:
            try:
                hunt_loop(config_loader, db)
            finally:
                with self._lock:
                    self._want_running = False
                    if self.stats.run_state != "paused_thermal":
                        self.stats.run_state = "stopped"
                    self._hunt_thread = None

        thread = threading.Thread(target=_target, name="job-hunter-loop", daemon=True)
        with self._lock:
            self._hunt_thread = thread
        thread.start()
        self.record("status", message="Hunt started")
        return {"ok": True, "run_state": "running"}

    def request_stop(self) -> dict[str, Any]:
        with self._lock:
            self._want_running = False
            self.stats.run_state = "stopping"
            self.stats.pause_reason = "stopped by user"
            self._stop_cycle.set()
        self.record("status", message="Hunt stop requested")
        return {"ok": True, "run_state": "stopping"}


# Singleton used by job hunter + sync dashboard routes
hunter_state = HunterState()
