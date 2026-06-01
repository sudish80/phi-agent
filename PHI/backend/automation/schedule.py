import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "workspace",
    "schedules.json",
)


@dataclass
class ScheduleEntry:
    id: str = ""
    time: str = ""
    action: str = ""
    params: dict = field(default_factory=dict)
    day_of_week: Optional[int] = None
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduleEntry":
        return cls(
            id=data.get("id", ""),
            time=data.get("time", ""),
            action=data.get("action", ""),
            params=data.get("params", {}),
            day_of_week=data.get("day_of_week"),
            active=data.get("active", True),
            created_at=data.get("created_at", ""),
        )

    def is_due(self) -> bool:
        if not self.active:
            return False
        now = datetime.now(timezone.utc)
        current_time = now.strftime("%H:%M")
        if self.day_of_week is not None and now.weekday() != self.day_of_week:
            return False
        return current_time == self.time


class ScheduleManager:
    def __init__(self, storage_path: str = DEFAULT_SCHEDULE_PATH):
        self.storage_path = storage_path
        self._entries: dict[str, ScheduleEntry] = {}
        self._lock = Lock()
        self._ensure_file()
        self._load()

    def _ensure_file(self):
        dir_path = os.path.dirname(self.storage_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w") as f:
                json.dump([], f)

    def _load(self):
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            with self._lock:
                self._entries = {e["id"]: ScheduleEntry.from_dict(e) for e in data}
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning("Could not load schedules: %s", e)
            self._entries = {}

    def _save(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump([e.to_dict() for e in self._entries.values()], f, indent=2)
        except OSError as e:
            logger.error("Failed to save schedules: %s", e)

    def add_schedule(self, entry: ScheduleEntry) -> str:
        if not entry.id:
            entry.id = f"schedule_{int(time.time() * 1000)}"
        with self._lock:
            self._entries[entry.id] = entry
            self._save()
        logger.info("Added schedule '%s' (%s)", entry.id, entry.action)
        return entry.id

    def remove_schedule(self, entry_id: str) -> bool:
        with self._lock:
            removed = self._entries.pop(entry_id, None)
            if removed:
                self._save()
                logger.info("Removed schedule '%s'", entry_id)
            return removed is not None

    def get_schedule(self, entry_id: str) -> Optional[ScheduleEntry]:
        with self._lock:
            return self._entries.get(entry_id)

    def list_schedules(self, active_only: bool = False) -> list[ScheduleEntry]:
        with self._lock:
            entries = list(self._entries.values())
        if active_only:
            entries = [e for e in entries if e.active]
        return sorted(entries, key=lambda e: e.time)

    def check_due(self) -> list[ScheduleEntry]:
        with self._lock:
            entries = list(self._entries.values())
        due = [e for e in entries if e.is_due()]
        if due:
            logger.info("Found %d due schedule(s)", len(due))
        return due

    def toggle_active(self, entry_id: str, active: bool) -> bool:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.active = active
                self._save()
                logger.info("Set schedule '%s' active=%s", entry_id, active)
                return True
        return False


_manager = ScheduleManager()


def get_schedule_manager() -> ScheduleManager:
    return _manager


def add_schedule(entry: ScheduleEntry) -> str:
    return _manager.add_schedule(entry)


def remove_schedule(entry_id: str) -> bool:
    return _manager.remove_schedule(entry_id)


def check_due() -> list[ScheduleEntry]:
    return _manager.check_due()
