"""Canvas block persistence — SQLite backend for canvases and blocks."""

import json
import os
import time
import logging
from typing import Any, Dict, List, Optional

import aiosqlite

from backend.canvas.models import Canvas, CanvasBlock, CanvasType, BlockType

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "canvas_blocks.db",
)


class CanvasStore:
    """Persistent canvas storage with SQLite backend."""

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
                CREATE TABLE IF NOT EXISTS canvases (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'text',
                    content TEXT NOT NULL DEFAULT '',
                    position TEXT,
                    size TEXT,
                    z_index INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS canvas_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canvas_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    snapshot TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (canvas_id) REFERENCES canvases(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS canvas_blocks (
                    id TEXT PRIMARY KEY,
                    canvas_id TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'text',
                    content TEXT NOT NULL DEFAULT '',
                    language TEXT,
                    locked_by TEXT,
                    collaborators TEXT NOT NULL DEFAULT '[]',
                    position TEXT,
                    size TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (canvas_id) REFERENCES canvases(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_canvases_thread
                    ON canvases(thread_id);
                CREATE INDEX IF NOT EXISTS idx_blocks_canvas
                    ON canvas_blocks(canvas_id);
                CREATE INDEX IF NOT EXISTS idx_versions_canvas
                    ON canvas_versions(canvas_id, version);
            """)
            await conn.commit()
        finally:
            await conn.close()

    # ── Canvas CRUD ─────────────────────────────────────────────

    async def create_canvas(self, canvas: Canvas) -> Canvas:
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO canvases (id, thread_id, type, content, position, size, z_index, created_at, updated_at, version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    canvas.id,
                    canvas.thread_id,
                    canvas.type.value,
                    canvas.content,
                    json.dumps(canvas.position) if canvas.position else None,
                    json.dumps(canvas.size) if canvas.size else None,
                    canvas.z_index,
                    canvas.created_at,
                    canvas.updated_at,
                    canvas.version,
                ),
            )
            await conn.commit()
            return canvas
        finally:
            await conn.close()

    async def get_canvas(self, canvas_id: str) -> Optional[Canvas]:
        conn = await self._connect()
        try:
            row = await conn.execute(
                "SELECT * FROM canvases WHERE id=?", (canvas_id,)
            )
            row = await row.fetchone()
            if not row:
                return None
            return self._row_to_canvas(row)
        finally:
            await conn.close()

    async def list_canvases(
        self, thread_id: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[Canvas]:
        conn = await self._connect()
        try:
            if thread_id:
                cursor = await conn.execute(
                    "SELECT * FROM canvases WHERE thread_id=? ORDER BY z_index ASC, created_at ASC LIMIT ? OFFSET ?",
                    (thread_id, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM canvases ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            rows = await cursor.fetchall()
            return [self._row_to_canvas(r) for r in rows]
        finally:
            await conn.close()

    async def update_canvas(self, canvas: Canvas) -> Optional[Canvas]:
        conn = await self._connect()
        try:
            canvas.updated_at = time.time()
            canvas.version += 1
            await conn.execute(
                "UPDATE canvases SET type=?, content=?, position=?, size=?, z_index=?, "
                "updated_at=?, version=? WHERE id=?",
                (
                    canvas.type.value,
                    canvas.content,
                    json.dumps(canvas.position) if canvas.position else None,
                    json.dumps(canvas.size) if canvas.size else None,
                    canvas.z_index,
                    canvas.updated_at,
                    canvas.version,
                    canvas.id,
                ),
            )
            await conn.commit()
            return canvas
        finally:
            await conn.close()

    async def delete_canvas(self, canvas_id: str) -> bool:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "DELETE FROM canvases WHERE id=?", (canvas_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # ── Canvas Block CRUD ──────────────────────────────────────

    async def create_block(self, block: CanvasBlock) -> CanvasBlock:
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO canvas_blocks (id, canvas_id, type, content, language, locked_by, "
                "collaborators, position, size, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    block.id,
                    block.canvas_id,
                    block.type.value,
                    block.content,
                    block.language,
                    block.locked_by,
                    json.dumps(block.collaborators),
                    json.dumps(block.position) if block.position else None,
                    json.dumps(block.size) if block.size else None,
                    json.dumps(block.metadata),
                ),
            )
            await conn.commit()
            return block
        finally:
            await conn.close()

    async def get_block(self, block_id: str) -> Optional[CanvasBlock]:
        conn = await self._connect()
        try:
            row = await conn.execute(
                "SELECT * FROM canvas_blocks WHERE id=?", (block_id,)
            )
            row = await row.fetchone()
            if not row:
                return None
            return self._row_to_block(row)
        finally:
            await conn.close()

    async def list_blocks(self, canvas_id: str) -> List[CanvasBlock]:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT * FROM canvas_blocks WHERE canvas_id=? ORDER BY rowid",
                (canvas_id,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_block(r) for r in rows]
        finally:
            await conn.close()

    async def update_block(self, block: CanvasBlock) -> Optional[CanvasBlock]:
        conn = await self._connect()
        try:
            await conn.execute(
                "UPDATE canvas_blocks SET type=?, content=?, language=?, locked_by=?, "
                "collaborators=?, position=?, size=?, metadata=? WHERE id=?",
                (
                    block.type.value,
                    block.content,
                    block.language,
                    block.locked_by,
                    json.dumps(block.collaborators),
                    json.dumps(block.position) if block.position else None,
                    json.dumps(block.size) if block.size else None,
                    json.dumps(block.metadata),
                    block.id,
                ),
            )
            await conn.commit()
            return block
        finally:
            await conn.close()

    async def delete_block(self, block_id: str) -> bool:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "DELETE FROM canvas_blocks WHERE id=?", (block_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # ── Block operations ────────────────────────────────────────

    async def update_block_content(
        self, block_id: str, content: str
    ) -> Optional[CanvasBlock]:
        block = await self.get_block(block_id)
        if not block:
            return None
        block.content = content
        return await self.update_block(block)

    async def lock_block(self, block_id: str, user: str) -> bool:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "UPDATE canvas_blocks SET locked_by=? WHERE id=? AND locked_by IS NULL",
                (user, block_id),
            )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    async def unlock_block(self, block_id: str, user: Optional[str] = None) -> bool:
        conn = await self._connect()
        try:
            if user:
                cursor = await conn.execute(
                    "UPDATE canvas_blocks SET locked_by=NULL WHERE id=? AND locked_by=?",
                    (block_id, user),
                )
            else:
                cursor = await conn.execute(
                    "UPDATE canvas_blocks SET locked_by=NULL WHERE id=?",
                    (block_id,),
                )
            await conn.commit()
            return cursor.rowcount > 0
        finally:
            await conn.close()

    # ── Versioning ───────────────────────────────────────────────

    async def save_version(self, canvas_id: str) -> int:
        canvas = await self.get_canvas(canvas_id)
        if not canvas:
            return 0
        blocks = await self.list_blocks(canvas_id)
        snapshot = {
            "content": canvas.content,
            "blocks": [
                {
                    "id": b.id,
                    "type": b.type.value,
                    "content": b.content,
                    "language": b.language,
                    "position": b.position,
                    "size": b.size,
                }
                for b in blocks
            ],
        }
        conn = await self._connect()
        try:
            await conn.execute(
                "INSERT INTO canvas_versions (canvas_id, version, content, snapshot, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (canvas_id, canvas.version, canvas.content, json.dumps(snapshot), time.time()),
            )
            await conn.commit()
            return canvas.version
        finally:
            await conn.close()

    async def get_versions(self, canvas_id: str) -> List[Dict[str, Any]]:
        conn = await self._connect()
        try:
            cursor = await conn.execute(
                "SELECT version, content, created_at FROM canvas_versions "
                "WHERE canvas_id=? ORDER BY version DESC",
                (canvas_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    async def restore_version(self, canvas_id: str, version: int) -> Optional[Canvas]:
        conn = await self._connect()
        try:
            row = await conn.execute(
                "SELECT * FROM canvas_versions WHERE canvas_id=? AND version=?",
                (canvas_id, version),
            )
            row = await row.fetchone()
            if not row:
                return None
            snapshot = json.loads(row["snapshot"])
            canvas = await self.get_canvas(canvas_id)
            if not canvas:
                return None
            canvas.content = snapshot.get("content", row["content"])
            canvas.version = version
            canvas.updated_at = time.time()
            await self.update_canvas(canvas)
            return canvas
        finally:
            await conn.close()

    async def diff_versions(
        self, canvas_id: str, v1: int, v2: int
    ) -> Optional[Dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.execute(
                "SELECT version, snapshot FROM canvas_versions "
                "WHERE canvas_id=? AND version IN (?, ?) ORDER BY version",
                (canvas_id, v1, v2),
            )
            rows = await rows.fetchall()
            if len(rows) != 2:
                return None
            snap1 = json.loads(rows[0]["snapshot"]) if rows[0]["snapshot"] else {}
            snap2 = json.loads(rows[1]["snapshot"]) if rows[1]["snapshot"] else {}
            return {
                "canvas_id": canvas_id,
                "from_version": v1,
                "to_version": v2,
                "content_changed": snap1.get("content") != snap2.get("content"),
                "blocks_added": len(snap2.get("blocks", [])) - len(snap1.get("blocks", [])),
            }
        finally:
            await conn.close()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _row_to_canvas(row) -> Canvas:
        return Canvas(
            id=row["id"],
            thread_id=row["thread_id"],
            type=CanvasType(row["type"]),
            content=row["content"] or "",
            position=json.loads(row["position"]) if row["position"] else None,
            size=json.loads(row["size"]) if row["size"] else None,
            z_index=row["z_index"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            version=row["version"],
        )

    @staticmethod
    def _row_to_block(row) -> CanvasBlock:
        return CanvasBlock(
            id=row["id"],
            canvas_id=row["canvas_id"],
            type=BlockType(row["type"]),
            content=row["content"] or "",
            language=row["language"],
            locked_by=row["locked_by"],
            collaborators=json.loads(row["collaborators"] or "[]"),
            position=json.loads(row["position"]) if row["position"] else None,
            size=json.loads(row["size"]) if row["size"] else None,
            metadata=json.loads(row["metadata"] or "{}"),
        )


canvas_store = CanvasStore()
