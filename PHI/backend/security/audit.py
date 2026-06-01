import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = ""
    action: str = ""
    details: dict = field(default_factory=dict)
    success: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        return cls(
            timestamp=data.get("timestamp", ""),
            session_id=data.get("session_id", ""),
            action=data.get("action", ""),
            details=data.get("details", {}),
            success=data.get("success", True),
        )


class AuditStore:
    def __init__(self, json_path: Optional[str] = None):
        self._entries: list[AuditEntry] = []
        self._lock = Lock()
        self.json_path = json_path
        if json_path:
            self._ensure_file()
            self._load()

    def _ensure_file(self):
        dir_path = os.path.dirname(self.json_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        if not os.path.exists(self.json_path):
            with open(self.json_path, "w") as f:
                json.dump([], f)

    def _load(self):
        try:
            with open(self.json_path, "r") as f:
                data = json.load(f)
            with self._lock:
                self._entries = [AuditEntry.from_dict(e) for e in data]
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning("Could not load audit log: %s", e)
            self._entries = []

    def append(self, entry: AuditEntry):
        with self._lock:
            self._entries.append(entry)
            if self.json_path:
                self._flush()
        logger.debug("Audit: %s | %s | success=%s", entry.session_id, entry.action, entry.success)

    def _flush(self):
        try:
            with open(self.json_path, "w") as f:
                json.dump([e.to_dict() for e in self._entries], f, indent=2)
        except OSError as e:
            logger.error("Failed to write audit log: %s", e)

    def get_entries(self, session_id: Optional[str] = None, action: Optional[str] = None, limit: int = 100) -> list[AuditEntry]:
        with self._lock:
            results = list(self._entries)
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if action:
            results = [e for e in results if e.action == action]
        return results[-limit:]

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def clear(self):
        with self._lock:
            self._entries.clear()
            if self.json_path:
                self._flush()


_store = AuditStore()


def log_action(session_id: str, action: str, details: dict = None, success: bool = True, store: Optional[AuditStore] = None) -> AuditEntry:
    entry = AuditEntry(
        session_id=session_id,
        action=action,
        details=details or {},
        success=success,
    )
    s = store or _store
    s.append(entry)
    return entry


def get_audit_store() -> AuditStore:
    return _store


def configure_audit_store(json_path: str):
    global _store
    _store = AuditStore(json_path=json_path)
