"""Thread persistence — SQLite backend for threads and messages."""

import json
import os
import time
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from backend.canvas.models import Thread, ThreadMessage, ThreadStatus

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "canvas_threads.db",
)


class ThreadStore:
    """Persistent thread storage with SQLite backend."""

    def __init__(self, db_path: str = _DB_PATH):
        self._db_path = db_path

    async def _connect(self) -> aiosqlite.Connection:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = await aiosqlite.connect(self._db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def ensure_schema(self) -> None:
        conn = await self._connect()
        try:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    tags TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    parent_thread_id TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    parent_id TEXT,
                    tool_calls TEXT,
                    tool_results TEXT,
                    attachments TEXT,
                    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_thread
                    ON messages(thread_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_threads_status
                    ON threads(status);
                CREATE INDEX IF NOT EXISTS idx_threads_updated
                    ON threads(updated_at);
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content, thread_id, content=messages, content_rowid=rowid
                );
                CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                    INSERT INTO messages_fts(rowid, content, thread_id)
                    VALUES (new.rowid, new.content, new.thread_id);
                END;
                CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content, thread_id)
                    VALUES ('delete', old.rowid, old.content, old.thread_id);
                END;
                CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content, thread_id)
                    VALUES ('delete', old.rowid, old.content, old.thread_id);
                    INSERT INTO messages_fts(rowid, content, thread_id)
                    VALUES (new.rowid, new.content, new.thread_id);
                END;
            """)
            await conn.commit()
        finally:
            await conn.close()

    # ── Thread CRUD ──────────────────────────────────────────────

    async def create_thread(self, thread: Thread) -> Thread:
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO threads (id, title, created_at, updated_at, status, tags, metadata, parent_thread_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    thread.id,
                    thread.title,
                    thread.created_at,
                    thread.updated_at,
                    thread.status.value,
                    json.dumps(thread.tags),
                    json.dumps(thread.metadata),
                    thread.parent_thread_id,
                ),
            )
            await conn.commit()
            return thread
        finally:
            await conn.close()

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        conn = await self._connect()
        try:
            row = await conn.execute(
                "SELECT * FROM threads WHERE id=?", (thread_id,)
            )
            row = await row.fetchone()
            if not row:
                return None
            return self._row_to_thread(row)
        finally:
            await conn.close()

    async def list_threads(
        self,
        status: Optional[ThreadStatus] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Thread]:
        conn = await self._connect()
        try:
            query = "SELECT * FROM threads"
            params: List[Any] = []
            conditions = []
            if status:
                conditions.append("status=?")
                params.append(status.value)
            if tags:
                placeholders = ",".join("?" for _ in tags)
                conditions.append(
                    f"EXISTS (SELECT 1 FROM json_each(tags) WHERE value IN ({placeholders}))"
                )
                params.extend(tags)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_thread(r) for r in rows]
        finally:
            await conn.close()

    async def update_thread(self, thread: Thread) -> Optional[Thread]:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE threads SET title=?, updated_at=?, status=?, tags=?, metadata=?, parent_thread_id=? "
                "WHERE id=?",
                (
                    thread.title,
                    thread.updated_at,
                    thread.status.value,
                    json.dumps(thread.tags),
                    json.dumps(thread.metadata),
                    thread.parent_thread_id,
                    thread.id,
                ),
            )
            await conn.commit()
            return thread
        finally:
            await conn.close()

    async def archive_thread(self, thread_id: str) -> bool:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "UPDATE threads SET status='archived', updated_at=? WHERE id=? AND status='active'",
                (time.time(), thread_id),
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    async def delete_thread(self, thread_id: str) -> bool:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "DELETE FROM threads WHERE id=?", (thread_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # ── Message CRUD ────────────────────────────────────────────

    async def add_message(self, msg: ThreadMessage) -> ThreadMessage:
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO messages (id, thread_id, role, content, timestamp, parent_id, "
                "tool_calls, tool_results, attachments) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    msg.id,
                    msg.thread_id,
                    msg.role,
                    msg.content,
                    msg.timestamp,
                    msg.parent_id,
                    json.dumps(msg.tool_calls or []),
                    json.dumps(msg.tool_results or []),
                    json.dumps(msg.attachments or []),
                ),
            )
            await conn.execute(
                "UPDATE threads SET updated_at=? WHERE id=?",
                (msg.timestamp, msg.thread_id),
            )
            await conn.commit()
            return msg
        finally:
            await conn.close()

    async def get_messages(
        self,
        thread_id: str,
        limit: int = 100,
        offset: int = 0,
        before: Optional[float] = None,
    ) -> List[ThreadMessage]:
        conn = await self._connect()
        try:
            query = "SELECT * FROM messages WHERE thread_id=?"
            params: List[Any] = [thread_id]
            if before is not None:
                query += " AND timestamp < ?"
                params.append(before)
            query += " ORDER BY timestamp ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_message(r) for r in rows]
        finally:
            await conn.close()

    async def update_message(self, msg: ThreadMessage) -> Optional[ThreadMessage]:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE messages SET role=?, content=?, parent_id=?, "
                "tool_calls=?, tool_results=?, attachments=? WHERE id=?",
                (
                    msg.role,
                    msg.content,
                    msg.parent_id,
                    json.dumps(msg.tool_calls or []),
                    json.dumps(msg.tool_results or []),
                    json.dumps(msg.attachments or []),
                    msg.id,
                ),
            )
            await conn.commit()
            return msg
        finally:
            await conn.close()

    async def delete_message(self, msg_id: str) -> bool:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "DELETE FROM messages WHERE id=?", (msg_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # ── Search & Summary ────────────────────────────────────────

    async def search_messages(self, text: str, limit: int = 50) -> List[Tuple[str, str, str, float]]:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT m.id, m.thread_id, m.content, m.timestamp "
                "FROM messages_fts f JOIN messages m ON f.rowid = m.rowid "
                "WHERE messages_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (text, limit),
            )
            rows = await cursor.fetchall()
            return [(r["id"], r["thread_id"], r["content"], r["timestamp"]) for r in rows]
        finally:
            await conn.close()

    async def get_thread_summary(self, thread_id: str) -> Optional[Dict[str, Any]]:
        conn = await self._connect()
        try:
            thread = await self.get_thread(thread_id)
            if not thread:
                return None
            cursor = await conn.execute(
                "SELECT COUNT(*) as msg_count, MAX(timestamp) as last_activity "
                "FROM messages WHERE thread_id=?",
                (thread_id,),
            )
            row = await cursor.fetchone()
            cursor2 = await conn.execute(
                "SELECT DISTINCT role FROM messages WHERE thread_id=?",
                (thread_id,),
            )
            roles = [r["role"] for r in await cursor2.fetchall()]
            return {
                "thread_id": thread_id,
                "title": thread.title,
                "status": thread.status.value,
                "message_count": row["msg_count"] if row else 0,
                "last_activity": row["last_activity"] if row else None,
                "participants": roles,
                "tags": thread.tags,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
            }
        finally:
            await conn.close()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _row_to_thread(row) -> Thread:
        return Thread(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=ThreadStatus(row["status"]),
            tags=json.loads(row["tags"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            parent_thread_id=row["parent_thread_id"],
        )

    @staticmethod
    def _row_to_message(row) -> ThreadMessage:
        return ThreadMessage(
            id=row["id"],
            thread_id=row["thread_id"],
            role=row["role"],
            content=row["content"],
            timestamp=row["timestamp"],
            parent_id=row["parent_id"],
            tool_calls=json.loads(row["tool_calls"] or "[]") or None,
            tool_results=json.loads(row["tool_results"] or "[]") or None,
            attachments=json.loads(row["attachments"] or "[]") or None,
        )


thread_store = ThreadStore()
