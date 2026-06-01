import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "workspace", "companion_memory")


@dataclass
class CompanionMemory:
    user_id: str = ""
    facts: list[str] = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    interaction_history_summaries: list[str] = field(default_factory=list)
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CompanionMemory":
        return cls(
            user_id=data.get("user_id", ""),
            facts=data.get("facts", []),
            preferences=data.get("preferences", {}),
            interaction_history_summaries=data.get("interaction_history_summaries", []),
            last_updated=data.get("last_updated", datetime.now(timezone.utc).isoformat()),
        )

    def add_fact(self, fact: str):
        if fact not in self.facts:
            self.facts.append(fact)
            self.last_updated = datetime.now(timezone.utc).isoformat()

    def add_summary(self, summary: str):
        self.interaction_history_summaries.append(summary)
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def set_preference(self, key: str, value):
        self.preferences[key] = value
        self.last_updated = datetime.now(timezone.utc).isoformat()


def extract_facts(text: str) -> list[str]:
    facts = []
    patterns = [
        r"(?:my name is|I'm|I am|call me)\s+(\w+)",
        r"I (?:like|love|enjoy|prefer)\s+(.+?)(?:\.|,|$)",
        r"I (?:don't|do not) (?:like|enjoy|prefer)\s+(.+?)(?:\.|,|$)",
        r"I (?:work as|am a|am an)\s+(.+?)(?:\.|,|$)",
        r"I (?:live in|am from|am based in)\s+(.+?)(?:\.|,|$)",
        r"my (?:favorite|favourite)\s+(.+?)(?:\s+is)\s+(.+?)(?:\.|,|$)",
        r"I (?:have|own|use)\s+(.+?)(?:\.|,|$)",
    ]
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            fact = match.group(0).strip()
            if fact and len(fact) > 3:
                facts.append(fact)
    return facts


class MemoryManager:
    def __init__(self, storage_dir: str = DEFAULT_MEMORY_DIR):
        self.storage_dir = storage_dir
        self._cache: dict[str, CompanionMemory] = {}
        self._lock = Lock()
        os.makedirs(self.storage_dir, exist_ok=True)

    def _file_path(self, user_id: str) -> str:
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)
        return os.path.join(self.storage_dir, f"{safe_name}.json")

    def get_memory(self, user_id: str) -> CompanionMemory:
        with self._lock:
            if user_id in self._cache:
                return self._cache[user_id]
        file_path = self._file_path(user_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                mem = CompanionMemory.from_dict(data)
                with self._lock:
                    self._cache[user_id] = mem
                return mem
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Failed to load memory for %s: %s", user_id, e)
        mem = CompanionMemory(user_id=user_id)
        with self._lock:
            self._cache[user_id] = mem
        return mem

    def update_memory(self, user_id: str, facts: list[str] = None, preferences: dict = None, summaries: list[str] = None):
        mem = self.get_memory(user_id)
        if facts:
            for fact in facts:
                mem.add_fact(fact)
        if preferences:
            for k, v in preferences.items():
                mem.set_preference(k, v)
        if summaries:
            for s in summaries:
                mem.add_summary(s)
        self._save_memory(user_id, mem)
        return mem

    def _save_memory(self, user_id: str, memory: CompanionMemory):
        file_path = self._file_path(user_id)
        try:
            with open(file_path, "w") as f:
                json.dump(memory.to_dict(), f, indent=2)
            logger.debug("Saved memory for %s", user_id)
        except OSError as e:
            logger.error("Failed to save memory for %s: %s", user_id, e)

    def delete_memory(self, user_id: str):
        with self._lock:
            self._cache.pop(user_id, None)
        file_path = self._file_path(user_id)
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Deleted memory for %s", user_id)

    def list_users(self) -> list[str]:
        files = []
        if os.path.exists(self.storage_dir):
            files = [f.replace(".json", "") for f in os.listdir(self.storage_dir) if f.endswith(".json")]
        return files


_manager = MemoryManager()


def get_memory_manager() -> MemoryManager:
    return _manager


def get_memory(user_id: str) -> CompanionMemory:
    return _manager.get_memory(user_id)


def update_memory(user_id: str, facts: list[str] = None, preferences: dict = None, summaries: list[str] = None) -> CompanionMemory:
    return _manager.update_memory(user_id, facts=facts, preferences=preferences, summaries=summaries)
