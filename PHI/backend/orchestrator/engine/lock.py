"""Session Write Lock — concurrent access safety for session files.

Mirrors openclaw's session-write-lock.ts.
"""

import os
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SessionLock:
    session_id: str
    owner_id: str
    acquired_at: float
    ttl: float = 30.0


class SessionWriteLock:
    """Per-session write lock to prevent concurrent transcript modification."""

    def __init__(self, lock_dir: Optional[str] = None):
        self._locks: Dict[str, SessionLock] = {}
        self._lock = asyncio.Lock()
        self._lock_dir = lock_dir

    async def acquire(self, session_id: str, owner_id: str, ttl: float = 30.0) -> bool:
        async with self._lock:
            existing = self._locks.get(session_id)
            now = time.time()
            if existing:
                if existing.owner_id == owner_id:
                    existing.acquired_at = now
                    return True
                if now - existing.acquired_at < existing.ttl:
                    return False
                logger.warning("Lock expired for session %s, stealing", session_id)
            self._locks[session_id] = SessionLock(
                session_id=session_id, owner_id=owner_id,
                acquired_at=now, ttl=ttl,
            )
            return True

    async def release(self, session_id: str, owner_id: str) -> None:
        async with self._lock:
            lock = self._locks.get(session_id)
            if lock and lock.owner_id == owner_id:
                del self._locks[session_id]
                logger.debug("Released lock for session %s", session_id)

    async def is_locked(self, session_id: str) -> bool:
        async with self._lock:
            lock = self._locks.get(session_id)
            if not lock:
                return False
            if time.time() - lock.acquired_at > lock.ttl:
                del self._locks[session_id]
                return False
            return True

    async def get_owner(self, session_id: str) -> Optional[str]:
        async with self._lock:
            lock = self._locks.get(session_id)
            if lock and time.time() - lock.acquired_at <= lock.ttl:
                return lock.owner_id
            return None

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [sid for sid, lock in self._locks.items()
                   if now - lock.acquired_at > lock.ttl]
        for sid in expired:
            del self._locks[sid]
        return len(expired)


# Global singleton
session_write_lock = SessionWriteLock()
