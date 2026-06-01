"""
Real HTTP/HTTPS Download Engine
- Streaming downloads with progress tracking
- Resume support (Range headers)
- Bandwidth limiting (configurable)
- Concurrent download control
- Download queue management
- Real file streaming to disk
"""

import asyncio
import aiohttp
import aiofiles
import sqlite3
import json
import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from urllib.parse import urlparse
import threading

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')
DOWNLOAD_DIR = os.path.join(os.path.dirname(DB_PATH), 'downloads')


class BandwidthLimiter:
    """Token-bucket rate limiter for download bandwidth"""

    def __init__(self, max_bytes_per_sec: int = 2 * 1024 * 1024):
        self.max_rate = max_bytes_per_sec
        self.tokens = max_bytes_per_sec
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def set_rate(self, bytes_per_sec: int):
        self.max_rate = bytes_per_sec

    def acquire(self, bytes_needed: int, timeout: float = 5.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_rate, self.tokens + elapsed * self.max_rate)
                self.last_refill = now

                if self.tokens >= bytes_needed:
                    self.tokens -= bytes_needed
                    return True

            time.sleep(0.05)
        return False


class DownloadTask:
    """Track state of a single download"""

    def __init__(self, url: str, filename: str = None, path: str = None):
        self.url = url
        self.filename = filename or os.path.basename(urlparse(url).path) or 'download'
        self.path = path or DOWNLOAD_DIR
        self.filepath = os.path.join(self.path, self.filename)
        self.status = 'queued'
        self.progress = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed_bps = 0.0
        self.start_time = None
        self.end_time = None
        self.error = None
        self._cancelled = False
        self._paused = False
        self._resume_pos = 0
        self._session = None


class DownloadEngine:
    """Real HTTP/HTTPS download engine"""

    def __init__(self, max_concurrent: int = 3, max_bandwidth: int = 2 * 1024 * 1024):
        self.max_concurrent = max_concurrent
        self.bandwidth_limiter = BandwidthLimiter(max_bandwidth)
        self.queue = []
        self.active = []
        self.completed = []
        self._id_counter = 0
        self._lock = threading.Lock()
        self._init_db()
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("CREATE TABLE IF NOT EXISTS download_engine_history ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                     "user_id INTEGER NOT NULL,"
                     "url TEXT NOT NULL,"
                     "filename TEXT,"
                     "filepath TEXT,"
                     "total_bytes INTEGER DEFAULT 0,"
                     "status TEXT DEFAULT 'queued',"
                     "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
        conn.close()

    def set_bandwidth(self, mbps: float):
        self.bandwidth_limiter.set_rate(int(mbps * 1024 * 1024))

    def set_concurrency(self, max_concurrent: int):
        self.max_concurrent = max_concurrent

    def queue_download(self, user_id: int, url: str, filename: str = None,
                      path: str = None) -> Dict:
        """Add a download to the queue"""
        with self._lock:
            self._id_counter += 1
            task_id = self._id_counter

            task = DownloadTask(url, filename, path)
            task.status = 'queued'
            task.user_id = user_id

            self.queue.append({'id': task_id, 'task': task})

            # Log to DB
            try:
                conn = sqlite3.connect(DB_PATH, timeout=10)
                conn.execute(
                    "INSERT INTO download_engine_history (user_id, url, filename, filepath, status) "
                    "VALUES (?, ?, ?, ?, 'queued')",
                    (user_id, url, task.filename, task.filepath)
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"DB log error: {e}")

            logger.info(f"Download queued [{task_id}]: {url} -> {task.filename}")

            return {
                'download_id': task_id,
                'filename': task.filename,
                'url': url,
                'status': 'queued'
            }

    async def _process_queue(self):
        """Process queued downloads (background)"""
        while True:
            with self._lock:
                # Check for new downloads to start
                while len(self.active) < self.max_concurrent and self.queue:
                    item = self.queue.pop(0)
                    self.active.append(item)

                    # Start download in background
                    asyncio.ensure_future(self._execute_download(item['id'], item['task']))

            await asyncio.sleep(0.5)

    async def _execute_download(self, task_id: int, task: DownloadTask):
        """Execute a single download"""
        task.status = 'downloading'
        task.start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if task._resume_pos > 0:
                    headers['Range'] = f'bytes={task._resume_pos}-'

                async with session.get(task.url, headers=headers, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status not in (200, 206):
                        task.status = 'error'
                        task.error = f'HTTP {resp.status}'
                        self._mark_completed(task_id, task)
                        return

                    total = int(resp.headers.get('Content-Length', 0)) + task._resume_pos
                    task.total_bytes = total

                    mode = 'ab' if task._resume_pos > 0 else 'wb'
                    async with aiofiles.open(task.filepath, mode) as f:
                        async for chunk in resp.content.iter_chunked(65536):
                            if task._cancelled:
                                task.status = 'cancelled'
                                self._mark_completed(task_id, task)
                                return

                            while task._paused:
                                await asyncio.sleep(0.2)
                                if task._cancelled:
                                    task.status = 'cancelled'
                                    self._mark_completed(task_id, task)
                                    return

                            if not self.bandwidth_limiter.acquire(len(chunk)):
                                continue

                            await f.write(chunk)
                            task.downloaded_bytes += len(chunk)

                            if total > 0:
                                task.progress = (task.downloaded_bytes / total) * 100

                            elapsed = time.time() - task.start_time
                            if elapsed > 0:
                                task.speed_bps = task.downloaded_bytes / elapsed

                task.status = 'completed'
                task.end_time = time.time()

        except asyncio.CancelledError:
            task.status = 'cancelled'
        except Exception as e:
            task.status = 'error'
            task.error = str(e)
            logger.error(f"Download error [{task_id}]: {e}")

        self._mark_completed(task_id, task)

    def _mark_completed(self, task_id: int, task: DownloadTask):
        """Move task from active to completed"""
        with self._lock:
            self.active = [a for a in self.active if a['id'] != task_id]
            self.completed.append({'id': task_id, 'task': task})

        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            conn.execute(
                "UPDATE download_engine_history SET status=?, total_bytes=? WHERE id=?",
                (task.status, task.downloaded_bytes, task_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB update error: {e}")

    def pause(self, download_id: int) -> Dict:
        """Pause a download"""
        for item in self.active:
            if item['id'] == download_id:
                item['task']._paused = True
                item['task'].status = 'paused'
                item['task']._resume_pos = item['task'].downloaded_bytes
                return {'status': 'paused', 'download_id': download_id}
        return {'status': 'error', 'message': 'Download not found'}

    def resume(self, download_id: int) -> Dict:
        """Resume a paused download"""
        for item in self.active:
            if item['id'] == download_id:
                item['task']._paused = False
                item['task'].status = 'downloading'
                return {'status': 'resumed', 'download_id': download_id}
        return {'status': 'error', 'message': 'Download not found'}

    def cancel(self, download_id: int) -> Dict:
        """Cancel a download"""
        for item in self.active:
            if item['id'] == download_id:
                item['task']._cancelled = True
                item['task'].status = 'cancelled'
                return {'status': 'cancelled', 'download_id': download_id}

        self.queue = [q for q in self.queue if q['id'] != download_id]
        return {'status': 'cancelled', 'download_id': download_id}

    def get_status(self, download_id: int) -> Dict:
        """Get status of a download"""
        for item in self.active:
            if item['id'] == download_id:
                t = item['task']
                return {
                    'download_id': download_id,
                    'filename': t.filename,
                    'status': t.status,
                    'progress': t.progress,
                    'downloaded_bytes': t.downloaded_bytes,
                    'total_bytes': t.total_bytes,
                    'speed_bps': t.speed_bps,
                    'speed_kbps': t.speed_bps / 1024,
                    'url': t.url
                }
        for item in self.queue:
            if item['id'] == download_id:
                return {
                    'download_id': download_id,
                    'filename': item['task'].filename,
                    'status': 'queued',
                    'progress': 0,
                    'url': item['task'].url
                }
        for item in self.completed:
            if item['id'] == download_id:
                t = item['task']
                return {
                    'download_id': download_id,
                    'filename': t.filename,
                    'status': t.status,
                    'progress': t.progress,
                    'total_bytes': t.total_bytes,
                    'downloaded_bytes': t.downloaded_bytes,
                    'speed_bps': t.speed_bps,
                    'url': t.url,
                    'error': t.error
                }
        return {'status': 'error', 'message': 'Download not found'}

    def list_downloads(self, user_id: int = None) -> List[Dict]:
        """List all downloads"""
        result = []
        for item in self.active:
            t = item['task']
            result.append({
                'id': item['id'],
                'filename': t.filename,
                'status': t.status,
                'progress': t.progress,
                'speed_kbps': t.speed_bps / 1024,
                'downloaded_mb': t.downloaded_bytes / 1024 / 1024,
                'total_mb': t.total_bytes / 1024 / 1024,
                'url': t.url
            })
        for item in self.queue:
            result.append({
                'id': item['id'],
                'filename': item['task'].filename,
                'status': 'queued',
                'progress': 0,
                'url': item['task'].url
            })
        for item in self.completed[-10:]:
            t = item['task']
            result.append({
                'id': item['id'],
                'filename': t.filename,
                'status': t.status,
                'progress': t.progress,
                'url': t.url
            })
        return result

    def get_stats(self) -> Dict:
        """Get download statistics"""
        with self._lock:
            total_downloads = self._id_counter
            active_count = len(self.active)
            queued_count = len(self.queue)
            completed_count = len(self.completed)
            active_downloaded = sum(item['task'].downloaded_bytes for item in self.active)
            total_speed = sum(item['task'].speed_bps for item in self.active)
            return {
                'total_downloads': total_downloads,
                'active': active_count,
                'queued': queued_count,
                'completed': completed_count,
                'active_downloaded_mb': active_downloaded / 1024 / 1024,
                'total_speed_kbps': total_speed / 1024
            }


# Global instance
download_engine = DownloadEngine()
