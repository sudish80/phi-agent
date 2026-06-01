"""Session persistence — stores session transcripts in SQLite."""

import json
import sqlite3
import os
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sessions.db')


@dataclass
class SessionRecord:
    session_id: str
    created_at: float = 0.0
    updated_at: float = 0.0
    message_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionStore:
    """Persistent session storage using SQLite."""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or '.', exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL,
                    updated_at REAL,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, timestamp)
            """)
            conn.commit()

    def save_session(self, session_id: str, metadata: Optional[Dict] = None) -> None:
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, created_at, updated_at, message_count, metadata) "
                "VALUES (?, COALESCE((SELECT created_at FROM sessions WHERE session_id=?), ?), ?, "
                "  (SELECT COALESCE(MAX(message_count),0) FROM sessions WHERE session_id=?), ?)",
                (session_id, session_id, now, now, session_id, json.dumps(metadata or {})),
            )
            conn.commit()

    def append_message(self, session_id: str, role: str, content: str) -> None:
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at=?, message_count=message_count+1 WHERE session_id=?",
                (now, session_id),
            )
            conn.commit()

    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content, timestamp FROM messages "
                "WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            message_count=row["message_count"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def list_sessions(self, limit: int = 20) -> List[SessionRecord]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [SessionRecord(
            session_id=r["session_id"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            message_count=r["message_count"],
            metadata=json.loads(r["metadata"] or "{}"),
        ) for r in rows]

    def delete_session(self, session_id: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            conn.commit()


session_store = SessionStore()
