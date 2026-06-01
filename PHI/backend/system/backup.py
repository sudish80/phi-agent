"""Backup and recovery system for the PHI AI agent.

Creates timestamped archives of databases, audio stores, memory stores,
workspace files, and configuration. Supports listing, restoring, deleting
backups, automatic scheduled backups, and cleanup of old backups.
"""

import os
import io
import json
import asyncio
import logging
import tarfile
import zipfile
import shutil
import tempfile
import platform
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from functools import lru_cache

from backend.system.config import system_config

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class BackupRecord:
    id: str
    timestamp: str
    label: str
    size_bytes: int
    file_count: int
    path: str = ""


@dataclass
class BackupManifest:
    id: str
    timestamp: str
    label: str
    files: List[str] = field(default_factory=list)
    total_size: int = 0


class BackupManager:
    """Singleton backup manager for creating, restoring, and managing backups."""

    _instance: Optional["BackupManager"] = None

    def __new__(cls) -> "BackupManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._backup_dir = system_config.backup_dir
        os.makedirs(self._backup_dir, exist_ok=True)
        self._background_task: Optional[asyncio.Task] = None
        self._backup_index_path = os.path.join(self._backup_dir, "backup_index.json")
        self._index: Dict[str, BackupManifest] = {}
        self._load_index()
        self._is_windows = platform.system() == "Windows"

    def _load_index(self) -> None:
        if os.path.exists(self._backup_index_path):
            try:
                with open(self._backup_index_path, "r") as f:
                    data = json.load(f)
                for bid, manifest in data.items():
                    self._index[bid] = BackupManifest(**manifest)
            except Exception as e:
                logger.warning("Failed to load backup index: %s", e)

    def _save_index(self) -> None:
        try:
            data = {bid: asdict(m) for bid, m in self._index.items()}
            with open(self._backup_index_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save backup index: %s", e)

    def _collect_sources(self) -> Dict[str, List[str]]:
        """Collect file paths categorized by source."""
        sources: Dict[str, List[str]] = {}

        db_dir = os.path.join(ROOT_DIR, "data")
        if os.path.isdir(db_dir):
            sources["databases"] = [
                os.path.join(db_dir, f)
                for f in os.listdir(db_dir)
                if f.endswith(".db") or f.endswith(".db-wal") or f.endswith(".db-shm")
            ]
        else:
            for label, db_path in [
                ("sessions.db", system_config.session_db_path),
                ("threads.db", system_config.thread_db_path),
                ("canvases.db", system_config.canvas_db_path),
            ]:
                if db_path and os.path.exists(db_path):
                    sources.setdefault("databases", []).append(db_path)
                    wal = db_path + "-wal"
                    shm = db_path + "-shm"
                    if os.path.exists(wal):
                        sources["databases"].append(wal)
                    if os.path.exists(shm):
                        sources["databases"].append(shm)

        audio_path = system_config.audio_store_path
        if audio_path and os.path.isdir(audio_path):
            audio_files = [
                os.path.join(audio_path, f)
                for f in os.listdir(audio_path)
                if os.path.isfile(os.path.join(audio_path, f))
            ]
            sources["audio"] = audio_files[:1000]

        memory_store = os.path.join(ROOT_DIR, "memory_store")
        if os.path.isdir(memory_store):
            memory_files = []
            for root, _, files in os.walk(memory_store):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        memory_files.append(fp)
            sources["memory"] = memory_files[:5000]

        companion_memory = os.path.join(ROOT_DIR, "companion_memory")
        if os.path.isdir(companion_memory):
            comp_files = []
            for root, _, files in os.walk(companion_memory):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        comp_files.append(fp)
            sources["companion_memory"] = comp_files[:2000]

        workspace_dir = os.path.join(ROOT_DIR, "workspace")
        if os.path.isdir(workspace_dir):
            ws_files = []
            for root, _, files in os.walk(workspace_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        ws_files.append(fp)
            sources["workspace"] = ws_files[:2000]

        env_file = os.path.join(ROOT_DIR, ".env")
        if os.path.exists(env_file):
            sources["config"] = [env_file]

        return sources

    async def create_backup(self, label: str = "") -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_backup_sync, label)

    def _create_backup_sync(self, label: str = "") -> str:
        backup_id = datetime.now(timezone.utc).strftime("backup_%Y%m%d_%H%M%S_%f")
        timestamp = datetime.now(timezone.utc).isoformat()
        if not label:
            label = f"Auto backup {timestamp}"

        backup_file = os.path.join(self._backup_dir, f"{backup_id}.{'zip' if self._is_windows else 'tar.gz'}")
        sources = self._collect_sources()
        all_files: List[str] = []
        for category, files in sources.items():
            all_files.extend(files)

        if self._is_windows:
            file_count = self._create_zip(backup_file, sources)
        else:
            file_count = self._create_targz(backup_file, sources)

        size_bytes = os.path.getsize(backup_file) if os.path.exists(backup_file) else 0

        manifest = BackupManifest(
            id=backup_id,
            timestamp=timestamp,
            label=label,
            files=[os.path.relpath(f, str(ROOT_DIR)) for f in all_files],
            total_size=size_bytes,
        )
        self._index[backup_id] = manifest
        self._save_index()

        logger.info(
            "Backup created: %s (%d files, %.2f MB)",
            backup_id, file_count, size_bytes / (1024 * 1024),
        )
        return backup_id

    def _create_zip(self, path: str, sources: Dict[str, List[str]]) -> int:
        count = 0
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for category, files in sources.items():
                for fp in files:
                    if os.path.isfile(fp):
                        arcname = f"{category}/{os.path.relpath(fp, str(ROOT_DIR))}".replace("\\", "/")
                        if fp.endswith(".env"):
                            self._add_redacted_env(zf, fp, arcname)
                        else:
                            zf.write(fp, arcname)
                        count += 1
        return count

    def _create_targz(self, path: str, sources: Dict[str, List[str]]) -> int:
        count = 0
        with tarfile.open(path, "w:gz") as tf:
            for category, files in sources.items():
                for fp in files:
                    if os.path.isfile(fp):
                        arcname = f"{category}/{os.path.relpath(fp, str(ROOT_DIR))}".replace("\\", "/")
                        if fp.endswith(".env"):
                            self._add_redacted_env_tar(tf, fp, arcname)
                        else:
                            tf.add(fp, arcname)
                        count += 1
        return count

    def _add_redacted_env(self, zf: zipfile.ZipFile, env_path: str, arcname: str) -> None:
        redacted_lines: List[str] = []
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, _ = line.split("=", 1)
                    key = key.strip()
                    if any(s in key.upper() for s in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                        redacted_lines.append(f"{key}=REDACTED\n")
                    else:
                        redacted_lines.append(line)
                else:
                    redacted_lines.append(line)
        redacted_content = "".join(redacted_lines)
        zf.writestr(arcname, redacted_content)

    def _add_redacted_env_tar(self, tf: tarfile.TarFile, env_path: str, arcname: str) -> None:
        redacted_lines: List[str] = []
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, _ = line.split("=", 1)
                    key = key.strip()
                    if any(s in key.upper() for s in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
                        redacted_lines.append(f"{key}=REDACTED\n")
                    else:
                        redacted_lines.append(line)
                else:
                    redacted_lines.append(line)
        redacted_content = "".join(redacted_lines).encode("utf-8")
        info = tarfile.TarInfo(name=arcname)
        info.size = len(redacted_content)
        info.mtime = int(datetime.now().timestamp())
        tf.addfile(info, io.BytesIO(redacted_content))

    def list_backups(self) -> List[BackupRecord]:
        records: List[BackupRecord] = []
        for bid, manifest in self._index.items():
            ext = ".zip" if self._is_windows else ".tar.gz"
            backup_path = os.path.join(self._backup_dir, f"{bid}{ext}")
            size = manifest.total_size
            if os.path.exists(backup_path):
                size = os.path.getsize(backup_path)
            records.append(BackupRecord(
                id=bid,
                timestamp=manifest.timestamp,
                label=manifest.label,
                size_bytes=size,
                file_count=len(manifest.files),
                path=backup_path,
            ))
        records.sort(key=lambda r: r.timestamp, reverse=True)
        return records

    def _get_backup_path(self, backup_id: str) -> Optional[str]:
        for ext in (".zip", ".tar.gz"):
            path = os.path.join(self._backup_dir, f"{backup_id}{ext}")
            if os.path.exists(path):
                return path
        return None

    def _extract_backup(self, backup_id: str, target_dir: str) -> int:
        path = self._get_backup_path(backup_id)
        if not path:
            raise FileNotFoundError(f"Backup file for {backup_id} not found")
        manifest = self._index.get(backup_id)
        if not manifest:
            raise ValueError(f"Backup {backup_id} not found in index")

        if path.endswith(".zip"):
            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(target_dir)
        else:
            with tarfile.open(path, "r:gz") as tf:
                tf.extractall(target_dir)

        count = 0
        for root, _, files in os.walk(target_dir):
            count += len(files)
        return count

    def restore_backup(self, backup_id: str, dry_run: bool = False) -> Dict:
        manifest = self._index.get(backup_id)
        if not manifest:
            raise ValueError(f"Backup {backup_id} not found in index")
        backup_path = self._get_backup_path(backup_id)
        if not backup_path:
            raise FileNotFoundError(f"Backup file for {backup_id} not found")

        with tempfile.TemporaryDirectory(prefix="phi_restore_") as tmpdir:
            extract_dir = os.path.join(tmpdir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            file_count = self._extract_backup(backup_id, extract_dir)

            if dry_run:
                return {
                    "backup_id": backup_id,
                    "label": manifest.label,
                    "timestamp": manifest.timestamp,
                    "file_count": file_count,
                    "dry_run": True,
                    "message": "Dry run completed, no files restored",
                }

            restored: List[str] = []
            skipped: List[str] = []
            errors: List[str] = []

            for root, _, files in os.walk(extract_dir):
                for fname in files:
                    src_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(src_path, extract_dir)
                    category_end = rel_path.find(os.sep)
                    category = rel_path[:category_end] if category_end > 0 else ""
                    file_rel = rel_path[category_end + 1:] if category_end > 0 else rel_path

                    if category == "config" and file_rel == ".env":
                        dest = os.path.join(ROOT_DIR, ".env")
                    elif category == "databases":
                        dest = os.path.join(ROOT_DIR, file_rel)
                    elif category == "audio":
                        dest = os.path.join(system_config.audio_store_path, os.path.basename(file_rel))
                    elif category == "memory":
                        dest = os.path.join(ROOT_DIR, file_rel)
                    elif category == "companion_memory":
                        dest = os.path.join(ROOT_DIR, file_rel)
                    elif category == "workspace":
                        dest = os.path.join(ROOT_DIR, file_rel)
                    else:
                        dest = os.path.join(ROOT_DIR, file_rel)

                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    try:
                        shutil.copy2(src_path, dest)
                        restored.append(rel_path)
                    except Exception as e:
                        errors.append(f"{rel_path}: {e}")

            logger.info(
                "Restored backup %s: %d files restored, %d skipped, %d errors",
                backup_id, len(restored), len(skipped), len(errors),
            )
            return {
                "backup_id": backup_id,
                "label": manifest.label,
                "timestamp": manifest.timestamp,
                "restored_count": len(restored),
                "error_count": len(errors),
                "errors": errors[:20],
            }

    def delete_backup(self, backup_id: str) -> bool:
        manifest = self._index.pop(backup_id, None)
        if not manifest:
            return False
        backup_path = self._get_backup_path(backup_id)
        if backup_path and os.path.exists(backup_path):
            os.remove(backup_path)
        self._save_index()
        logger.info("Deleted backup: %s", backup_id)
        return True

    def cleanup_old(self, keep_count: int = 10) -> int:
        records = self.list_backups()
        if len(records) <= keep_count:
            return 0
        to_delete = records[keep_count:]
        for r in to_delete:
            self.delete_backup(r.id)
        logger.info("Cleaned up %d old backups, keeping %d", len(to_delete), keep_count)
        return len(to_delete)

    async def auto_backup(self, interval_hours: int = 6) -> None:
        while True:
            try:
                backup_id = await self.create_backup(f"Auto backup {datetime.now(timezone.utc).isoformat()}")
                logger.info("Auto backup completed: %s", backup_id)
                self.cleanup_old(system_config.backup_keep_count)
            except Exception as e:
                logger.error("Auto backup failed: %s", e)
            await asyncio.sleep(interval_hours * 3600)

    def start_background(self, interval_hours: Optional[int] = None) -> None:
        if self._background_task and not self._background_task.done():
            logger.warning("Background backup task already running")
            return
        interval = interval_hours or system_config.backup_auto_interval_hours
        self._background_task = asyncio.create_task(self.auto_backup(interval))
        logger.info("Background backup started (interval=%dh)", interval)

    def stop_background(self) -> None:
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            self._background_task = None
            logger.info("Background backup stopped")


backup_manager = BackupManager()
