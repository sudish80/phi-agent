import os
import io
import json
import uuid
import logging
import hashlib
import asyncio
import zipfile
import shutil
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

import aiosqlite

from backend.audio.models import AudioEntry, AudioCategory, AudioSearchResult
from backend.shared.config import settings

logger = logging.getLogger(__name__)


class AudioManager:
    """Manages the full lifecycle of audio files: generation, storage, deduplication,
    compression, archival, memory linking, and search.

    Directory structure:
        audio/
        ├── generated/   (tts, responses, notifications, music, temporary)
        ├── recordings/  (conversations, commands, meetings)
        ├── processed/   (cleaned, normalized, compressed, embeddings)
        ├── cache/       (repeated_phrases, instant_responses)
        └── metadata/    (audio_index.db, transcripts.json)
    """

    def __init__(self, base_dir: Optional[str] = None):
        self._base_dir = Path(base_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "orchestrator", "static", "audio"
        ))
        self._db_path = self._base_dir / "metadata" / "audio_index.db"
        self._transcripts_path = self._base_dir / "metadata" / "transcripts.json"
        self._lock = asyncio.Lock()
        self._initialized = False

        self._dirs = {
            "generated/tts": self._base_dir / "generated" / "tts",
            "generated/responses": self._base_dir / "generated" / "responses",
            "generated/notifications": self._base_dir / "generated" / "notifications",
            "generated/music": self._base_dir / "generated" / "music",
            "generated/temporary": self._base_dir / "generated" / "temporary",
            "recordings/conversations": self._base_dir / "recordings" / "conversations",
            "recordings/commands": self._base_dir / "recordings" / "commands",
            "recordings/meetings": self._base_dir / "recordings" / "meetings",
            "processed/cleaned": self._base_dir / "processed" / "cleaned",
            "processed/normalized": self._base_dir / "processed" / "normalized",
            "processed/compressed": self._base_dir / "processed" / "compressed",
            "processed/embeddings": self._base_dir / "processed" / "embeddings",
            "cache/repeated_phrases": self._base_dir / "cache" / "repeated_phrases",
            "cache/instant_responses": self._base_dir / "cache" / "instant_responses",
        }
        self._archives_dir = self._base_dir / "archives"

    async def initialize(self):
        if self._initialized:
            return
        self._create_directories()
        await self._init_database()
        self._initialized = True
        logger.info(f"AudioManager initialized at {self._base_dir}")

    def _create_directories(self):
        for dir_path in self._dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        (self._base_dir / "metadata").mkdir(parents=True, exist_ok=True)
        self._archives_dir.mkdir(parents=True, exist_ok=True)

    async def _init_database(self):
        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audio_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    original_filename TEXT DEFAULT '',
                    file_size INTEGER DEFAULT 0,
                    format TEXT DEFAULT 'mp3',
                    duration_ms REAL DEFAULT 0.0,
                    category TEXT DEFAULT 'generated/tts',
                    subcategory TEXT DEFAULT '',
                    sha256_hash TEXT NOT NULL,
                    audio_url TEXT DEFAULT '',
                    transcript TEXT DEFAULT '',
                    speaker TEXT DEFAULT '',
                    emotion TEXT DEFAULT 'neutral',
                    sample_rate INTEGER DEFAULT 24000,
                    channels INTEGER DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}',
                    linked_conversation_id TEXT DEFAULT '',
                    linked_screenshot_id TEXT DEFAULT '',
                    linked_task_id TEXT DEFAULT '',
                    linked_thought_id TEXT DEFAULT '',
                    source TEXT DEFAULT 'elevenlabs',
                    is_compressed INTEGER DEFAULT 0,
                    archive_path TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    accessed_at TEXT DEFAULT '',
                    expires_at TEXT DEFAULT ''
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS compression_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audio_uuid TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT NULL,
                    error TEXT DEFAULT ''
                )
            """)
            try:
                await db.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS audio_fts USING fts5(
                        uuid UNINDEXED,
                        transcript,
                        speaker,
                        emotion,
                        category,
                        content='audio_files',
                        content_rowid='id'
                    )
                """)
            except Exception:
                pass
            try:
                await db.execute("""
                    CREATE TRIGGER IF NOT EXISTS audio_files_ai AFTER INSERT ON audio_files
                    BEGIN
                        INSERT INTO audio_fts(rowid, uuid, transcript, speaker, emotion, category)
                        VALUES (new.id, new.uuid, new.transcript, new.speaker, new.emotion, new.category);
                    END
                """)
            except Exception:
                pass
            try:
                await db.execute("""
                    CREATE TRIGGER IF NOT EXISTS audio_files_ad AFTER DELETE ON audio_files
                    BEGIN
                        INSERT INTO audio_fts(audio_fts, rowid, uuid, transcript, speaker, emotion, category)
                        VALUES ('delete', old.id, old.uuid, old.transcript, old.speaker, old.emotion, old.category);
                    END
                """)
            except Exception:
                pass
            try:
                await db.execute("""
                    CREATE TRIGGER IF NOT EXISTS audio_files_au AFTER UPDATE ON audio_files
                    BEGIN
                        INSERT INTO audio_fts(audio_fts, rowid, uuid, transcript, speaker, emotion, category)
                        VALUES ('delete', old.id, old.uuid, old.transcript, old.speaker, old.emotion, old.category);
                        INSERT INTO audio_fts(rowid, uuid, transcript, speaker, emotion, category)
                        VALUES (new.id, new.uuid, new.transcript, new.speaker, new.emotion, new.category);
                    END
                """)
            except Exception:
                pass
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_audio_category ON audio_files(category)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_audio_sha256 ON audio_files(sha256_hash)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_audio_created ON audio_files(created_at)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_audio_linked_conv ON audio_files(linked_conversation_id)
            """)
            await db.commit()

    def _compute_hash(self, audio_bytes: bytes) -> str:
        return hashlib.sha256(audio_bytes).hexdigest()

    def _get_category_dir(self, category: str) -> Path:
        return self._dirs.get(category, self._dirs["generated/tts"])

    async def store_audio(
        self,
        audio_bytes: bytes,
        format: str = "mp3",
        category: str = AudioCategory.GENERATED_TTS,
        transcript: str = "",
        speaker: str = "",
        emotion: str = "neutral",
        source: str = "elevenlabs",
        sample_rate: int = 24000,
        channels: int = 1,
        duration_ms: float = 0.0,
        linked_conversation_id: str = "",
        linked_screenshot_id: str = "",
        linked_task_id: str = "",
        linked_thought_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_hours: Optional[float] = None,
    ) -> Optional[AudioEntry]:
        audio_hash = self._compute_hash(audio_bytes)
        existing = await self._find_by_hash(audio_hash, category)
        if existing:
            logger.info(f"Duplicate audio found (hash={audio_hash[:12]}...) returning existing entry")
            return existing

        entry_id = uuid.uuid4().hex
        filename = f"{entry_id}.{format}"
        category_dir = self._get_category_dir(category)
        filepath = category_dir / filename
        filepath.write_bytes(audio_bytes)

        audio_url = f"/audio/{category}/{filename}"
        created_at = datetime.now(timezone.utc).isoformat()
        accessed_at = created_at
        expires_at = ""
        if expires_in_hours is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()

        entry = AudioEntry(
            uuid=entry_id,
            filename=str(Path(category) / filename),
            original_filename="",
            file_size=len(audio_bytes),
            format=format,
            duration_ms=duration_ms,
            category=category,
            subcategory="",
            sha256_hash=audio_hash,
            audio_url=audio_url,
            transcript=transcript,
            speaker=speaker,
            emotion=emotion,
            sample_rate=sample_rate,
            channels=channels,
            metadata_json=json.dumps(metadata or {}),
            linked_conversation_id=linked_conversation_id,
            linked_screenshot_id=linked_screenshot_id,
            linked_task_id=linked_task_id,
            linked_thought_id=linked_thought_id,
            source=source,
            is_compressed=False,
            archive_path="",
            created_at=created_at,
            accessed_at=accessed_at,
            expires_at=expires_at,
        )

        async with self._lock:
            async with aiosqlite.connect(str(self._db_path)) as db:
                await db.execute("""
                    INSERT INTO audio_files (
                        uuid, filename, original_filename, file_size, format,
                        duration_ms, category, subcategory, sha256_hash, audio_url,
                        transcript, speaker, emotion, sample_rate, channels,
                        metadata_json, linked_conversation_id, linked_screenshot_id,
                        linked_task_id, linked_thought_id, source, is_compressed,
                        archive_path, created_at, accessed_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.uuid, entry.filename, entry.original_filename, entry.file_size,
                    entry.format, entry.duration_ms, entry.category, entry.subcategory,
                    entry.sha256_hash, entry.audio_url, entry.transcript, entry.speaker,
                    entry.emotion, entry.sample_rate, entry.channels, entry.metadata_json,
                    entry.linked_conversation_id, entry.linked_screenshot_id,
                    entry.linked_task_id, entry.linked_thought_id, entry.source,
                    int(entry.is_compressed), entry.archive_path, entry.created_at,
                    entry.accessed_at, entry.expires_at,
                ))
                await db.commit()

        self._append_transcript(entry)
        logger.info(f"Stored audio: {filename} ({category}) — {transcript[:50] if transcript else 'no transcript'}")
        return entry

    async def _find_by_hash(self, sha256_hash: str, category: str) -> Optional[AudioEntry]:
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM audio_files WHERE sha256_hash = ? AND category = ? LIMIT 1",
                (sha256_hash, category)
            )
            row = await cursor.fetchone()
            if row:
                return AudioEntry.from_dict(dict(row))
        return None

    async def get_audio(self, audio_uuid: str) -> Optional[AudioEntry]:
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM audio_files WHERE uuid = ? LIMIT 1", (audio_uuid,)
            )
            row = await cursor.fetchone()
            if row:
                entry = AudioEntry.from_dict(dict(row))
                await db.execute(
                    "UPDATE audio_files SET accessed_at = ? WHERE uuid = ?",
                    (datetime.now(timezone.utc).isoformat(), audio_uuid)
                )
                await db.commit()
                return entry
        return None

    async def get_audio_path(self, audio_uuid: str) -> Optional[Path]:
        entry = await self.get_audio(audio_uuid)
        if not entry:
            return None
        path = self._base_dir / entry.filename
        if path.exists():
            return path
        if entry.archive_path:
            archive_path = Path(entry.archive_path)
            if archive_path.exists():
                return archive_path
        return None

    async def search(
        self,
        query: str = "",
        speaker: str = "",
        emotion: str = "",
        category: str = "",
        date_from: str = "",
        date_to: str = "",
        linked_conversation_id: str = "",
        linked_task_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[AudioSearchResult]:
        conditions = []
        params = []

        if query:
            conditions.append("audio_fts MATCH ?")
            params.append(query)
        if speaker:
            conditions.append("a.speaker = ?")
            params.append(speaker)
        if emotion:
            conditions.append("a.emotion = ?")
            params.append(emotion)
        if category:
            conditions.append("a.category = ?")
            params.append(category)
        if date_from:
            conditions.append("a.created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("a.created_at <= ?")
            params.append(date_to)
        if linked_conversation_id:
            conditions.append("a.linked_conversation_id = ?")
            params.append(linked_conversation_id)
        if linked_task_id:
            conditions.append("a.linked_task_id = ?")
            params.append(linked_task_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        if query:
            sql = f"""
                SELECT a.uuid, a.filename, a.category, a.transcript, a.speaker,
                       a.emotion, a.duration_ms, a.file_size, a.audio_url,
                       a.linked_conversation_id, a.created_at,
                       rank as score
                FROM audio_fts
                JOIN audio_files a ON audio_fts.rowid = a.id
                WHERE {where_clause}
                ORDER BY score
                LIMIT ? OFFSET ?
            """
        else:
            sql = f"""
                SELECT a.uuid, a.filename, a.category, a.transcript, a.speaker,
                       a.emotion, a.duration_ms, a.file_size, a.audio_url,
                       a.linked_conversation_id, a.created_at,
                       0.0 as score
                FROM audio_files a
                WHERE {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?
            """

        params.extend([limit, offset])

        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            return [AudioSearchResult(**dict(r)) for r in rows]

    async def delete_audio(self, audio_uuid: str) -> bool:
        entry = await self.get_audio(audio_uuid)
        if not entry:
            return False
        async with self._lock:
            async with aiosqlite.connect(str(self._db_path)) as db:
                await db.execute("DELETE FROM audio_files WHERE uuid = ?", (audio_uuid,))
                await db.commit()
        filepath = self._base_dir / entry.filename
        if filepath.exists():
            filepath.unlink()
        logger.info(f"Deleted audio: {audio_uuid}")
        return True

    async def compress_old_files(self, older_than_hours: float = 1.0):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat()
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM audio_files WHERE created_at < ? AND is_compressed = 0 AND archive_path = ''",
                (cutoff,)
            )
            rows = await cursor.fetchall()

        compressed_count = 0
        for row in rows:
            entry = AudioEntry.from_dict(dict(row))
            try:
                success = await self._compress_single(entry)
                if success:
                    compressed_count += 1
            except Exception as e:
                logger.warning(f"Failed to compress {entry.uuid}: {e}")

        if compressed_count:
            logger.info(f"Compressed {compressed_count} audio files older than {older_than_hours}h")
        return compressed_count

    async def _compress_single(self, entry: AudioEntry) -> bool:
        source_path = self._base_dir / entry.filename
        if not source_path.exists():
            return False

        archive_name = f"{entry.uuid[:8]}_{entry.category.replace('/', '_')}.zip"
        archive_path = self._archives_dir / archive_name

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(source_path, arcname=entry.filename)

        source_path.unlink()

        async with aiosqlite.connect(str(self._db_path)) as db:
            await db.execute(
                "UPDATE audio_files SET is_compressed = 1, archive_path = ? WHERE uuid = ?",
                (str(archive_path), entry.uuid)
            )
            await db.commit()

        logger.debug(f"Compressed {entry.uuid} → {archive_name}")
        return True

    async def cleanup_expired(self):
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(str(self._db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM audio_files WHERE expires_at != '' AND expires_at < ?",
                (now,)
            )
            rows = await cursor.fetchall()

        deleted = 0
        for row in rows:
            entry = AudioEntry.from_dict(dict(row))
            await self.delete_audio(entry.uuid)
            deleted += 1

        if deleted:
            logger.info(f"Cleaned up {deleted} expired audio files")
        return deleted

    async def cleanup_old_archives(self, retention_days: int = 7):
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        for archive_file in self._archives_dir.iterdir():
            if archive_file.suffix == ".zip":
                mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if mtime < cutoff:
                    archive_file.unlink()
                    logger.info(f"Deleted old archive: {archive_file.name}")

    def _append_transcript(self, entry: AudioEntry):
        if not entry.transcript:
            return
        try:
            if self._transcripts_path.exists():
                data = json.loads(self._transcripts_path.read_text(encoding="utf-8"))
            else:
                data = []
            data.append({
                "uuid": entry.uuid,
                "transcript": entry.transcript,
                "speaker": entry.speaker,
                "emotion": entry.emotion,
                "category": entry.category,
                "created_at": entry.created_at,
                "linked_conversation_id": entry.linked_conversation_id,
                "audio_url": entry.audio_url,
            })
            self._transcripts_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to write transcript: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM audio_files")
            total_files = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT COUNT(*) FROM audio_files WHERE is_compressed = 1")
            compressed = (await cursor.fetchone())[0]
            cursor = await db.execute("SELECT SUM(file_size) FROM audio_files")
            total_size = (await cursor.fetchone())[0] or 0
            cursor = await db.execute(
                "SELECT category, COUNT(*) as cnt FROM audio_files GROUP BY category ORDER BY cnt DESC"
            )
            by_category = {r[0]: r[1] for r in await cursor.fetchall()}

        return {
            "total_files": total_files,
            "compressed": compressed,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_category": by_category,
            "base_dir": str(self._base_dir),
            "db_path": str(self._db_path),
        }

    async def link_to_conversation(self, audio_uuid: str, conversation_id: str) -> bool:
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute(
                "UPDATE audio_files SET linked_conversation_id = ? WHERE uuid = ?",
                (conversation_id, audio_uuid)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def link_to_task(self, audio_uuid: str, task_id: str) -> bool:
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute(
                "UPDATE audio_files SET linked_task_id = ? WHERE uuid = ?",
                (task_id, audio_uuid)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def link_to_thought(self, audio_uuid: str, thought_id: str) -> bool:
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute(
                "UPDATE audio_files SET linked_thought_id = ? WHERE uuid = ?",
                (thought_id, audio_uuid)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def link_to_screenshot(self, audio_uuid: str, screenshot_id: str) -> bool:
        async with aiosqlite.connect(str(self._db_path)) as db:
            cursor = await db.execute(
                "UPDATE audio_files SET linked_screenshot_id = ? WHERE uuid = ?",
                (screenshot_id, audio_uuid)
            )
            await db.commit()
            return cursor.rowcount > 0
