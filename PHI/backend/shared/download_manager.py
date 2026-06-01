"""Intelligent Download Manager - Queue, throttle, and manage downloads with user assignments."""

import os
import threading
import time
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

class BandwidthLimiter:
    """Throttle downloads to specified bandwidth limits."""
    
    def __init__(self, kbps_limit: int = 1024):
        """
        Initialize bandwidth limiter.
        
        Args:
            kbps_limit: Maximum speed in KB/s (default 1024 = 1 MB/s)
        """
        self.kbps_limit = kbps_limit
        self.bytes_per_second = kbps_limit * 1024
        self.last_time = time.time()
        self.bytes_since_last_check = 0
    
    def throttle(self, bytes_downloaded: int):
        """Throttle download to maintain bandwidth limit."""
        current_time = time.time()
        elapsed = current_time - self.last_time
        
        if elapsed < 1.0:
            # Calculate bytes per second
            bytes_per_sec_actual = bytes_downloaded / elapsed if elapsed > 0 else 0
            
            if bytes_per_sec_actual > self.bytes_per_second:
                # Sleep to slow down
                sleep_time = (bytes_downloaded / self.bytes_per_second) - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        self.last_time = time.time()

class DownloadTask:
    """Represents a single download task."""
    
    def __init__(self, download_id: int, user_id: int, url: str, 
                 filepath: str, filename: str):
        self.download_id = download_id
        self.user_id = user_id
        self.url = url
        self.filepath = filepath
        self.filename = filename
        self.status = "pending"
        self.progress = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed_kbps = 0.0
        self.start_time = None
        self.end_time = None
        self.error = None
        self.paused = False
        self.cancelled = False
    
    def get_status_dict(self) -> Dict:
        """Get task status as dictionary."""
        return {
            "download_id": self.download_id,
            "user_id": self.user_id,
            "url": self.url,
            "filename": self.filename,
            "status": self.status,
            "progress": self.progress,
            "downloaded_mb": self.downloaded_bytes / (1024 * 1024),
            "total_mb": self.total_bytes / (1024 * 1024),
            "speed_kbps": self.speed_kbps,
            "paused": self.paused,
            "error": self.error
        }

class SmartDownloadManager:
    """Manage download queue with threading, bandwidth limiting, and persistence."""
    
    def __init__(self, max_concurrent: int = 3, bandwidth_kbps: int = 2048):
        """
        Initialize download manager.
        
        Args:
            max_concurrent: Maximum concurrent downloads (default 3)
            bandwidth_kbps: Total bandwidth limit in KB/s (default 2048 = 2 MB/s)
        """
        self.max_concurrent = max_concurrent
        self.bandwidth_kbps = bandwidth_kbps
        self.active_downloads = {}  # download_id -> DownloadTask
        self.download_queue = []
        self.running = False
        self.manager_thread = None
        self.lock = threading.Lock()
        self.bandwidth_limiter = BandwidthLimiter(bandwidth_kbps)
    
    def create_session(self) -> requests.Session:
        """Create requests session with retries."""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        return session
    
    def add_download(self, download_id: int, user_id: int, url: str,
                    filepath: str, filename: str) -> Dict:
        """Add download to queue."""
        with self.lock:
            task = DownloadTask(download_id, user_id, url, filepath, filename)
            self.download_queue.append(task)
            
            logger.info(f"Download added to queue: {filename}")
            
            return {
                "status": "queued",
                "message": f"Download queued: {filename}",
                "position": len(self.download_queue)
            }
    
    def download_file(self, task: DownloadTask, session: requests.Session) -> bool:
        """Download a single file with progress tracking."""
        try:
            task.status = "downloading"
            task.start_time = datetime.utcnow().isoformat()
            
            # Create directory if needed
            os.makedirs(os.path.dirname(task.filepath), exist_ok=True)
            
            # Start download with streaming
            with session.get(task.url, stream=True, timeout=30) as response:
                response.raise_for_status()
                
                # Get total file size
                task.total_bytes = int(response.headers.get('content-length', 0))
                
                # Download in chunks
                chunk_size = 8192  # 8KB chunks
                start_time = time.time()
                
                with open(task.filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if task.cancelled:
                            task.status = "cancelled"
                            os.remove(task.filepath)
                            return False
                        
                        if task.paused:
                            # Wait while paused
                            while task.paused and not task.cancelled:
                                time.sleep(1)
                            if task.cancelled:
                                return False
                        
                        if chunk:
                            f.write(chunk)
                            task.downloaded_bytes += len(chunk)
                            
                            # Calculate progress
                            if task.total_bytes > 0:
                                task.progress = (task.downloaded_bytes / task.total_bytes) * 100
                            
                            # Calculate speed
                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                task.speed_kbps = (task.downloaded_bytes / elapsed) / 1024
                            
                            # Apply bandwidth limiting
                            self.bandwidth_limiter.throttle(len(chunk))
            
            task.status = "completed"
            task.end_time = datetime.utcnow().isoformat()
            task.progress = 100.0
            
            logger.info(f"Download completed: {task.filename}")
            return True
        
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.end_time = datetime.utcnow().isoformat()
            logger.error(f"Download failed: {task.filename} - {e}")
            return False
    
    def process_queue(self):
        """Process download queue."""
        session = self.create_session()
        
        while self.running:
            with self.lock:
                # Check for completed/failed downloads
                active_count = len([t for t in self.active_downloads.values() 
                                   if t.status in ['downloading', 'paused']])
                
                # Start new downloads if slots available
                if active_count < self.max_concurrent and self.download_queue:
                    task = self.download_queue.pop(0)
                    self.active_downloads[task.download_id] = task
            
            # Execute downloads
            tasks_to_remove = []
            with self.lock:
                for download_id, task in list(self.active_downloads.items()):
                    if task.status == "downloading":
                        # Download in background
                        self.download_file(task, session)
                    
                    # Check if finished
                    if task.status in ["completed", "failed", "cancelled"]:
                        tasks_to_remove.append(download_id)
                
                # Clean up finished tasks
                for download_id in tasks_to_remove:
                    del self.active_downloads[download_id]
            
            time.sleep(0.5)
        
        session.close()
    
    def start(self):
        """Start the download manager."""
        if not self.running:
            self.running = True
            self.manager_thread = threading.Thread(target=self.process_queue, daemon=True)
            self.manager_thread.start()
            logger.info("Download manager started")
    
    def stop(self):
        """Stop the download manager."""
        self.running = False
        if self.manager_thread:
            self.manager_thread.join(timeout=5)
        logger.info("Download manager stopped")
    
    def pause_download(self, download_id: int) -> Dict:
        """Pause a download."""
        with self.lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id].paused = True
                return {"status": "paused", "download_id": download_id}
        
        return {"status": "error", "message": "Download not found"}
    
    def resume_download(self, download_id: int) -> Dict:
        """Resume a paused download."""
        with self.lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id].paused = False
                return {"status": "resumed", "download_id": download_id}
        
        return {"status": "error", "message": "Download not found"}
    
    def cancel_download(self, download_id: int) -> Dict:
        """Cancel a download."""
        with self.lock:
            if download_id in self.active_downloads:
                self.active_downloads[download_id].cancelled = True
                return {"status": "cancelled", "download_id": download_id}
        
        return {"status": "error", "message": "Download not found"}
    
    def get_download_status(self, download_id: int) -> Dict:
        """Get status of a specific download."""
        with self.lock:
            if download_id in self.active_downloads:
                return self.active_downloads[download_id].get_status_dict()
        
        return {"status": "error", "message": "Download not found"}
    
    def get_all_active_downloads(self) -> List[Dict]:
        """Get all active downloads."""
        with self.lock:
            return [task.get_status_dict() for task in self.active_downloads.values()]
    
    def get_queue_info(self) -> Dict:
        """Get download queue information."""
        with self.lock:
            return {
                "total_queued": len(self.download_queue),
                "total_active": len(self.active_downloads),
                "max_concurrent": self.max_concurrent,
                "bandwidth_limit_kbps": self.bandwidth_kbps,
                "active_downloads": [task.get_status_dict() for task in self.active_downloads.values()]
            }

# Global instance
download_manager = SmartDownloadManager(max_concurrent=3, bandwidth_kbps=2048)
