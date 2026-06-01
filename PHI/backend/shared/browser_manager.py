"""Web Browser Control System - Open websites and manage downloads."""

import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

def init_browser_db():
    """Initialize browser and download database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Browser history
        conn.execute('''
            CREATE TABLE IF NOT EXISTS browser_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                title TEXT,
                timestamp TEXT NOT NULL,
                duration_seconds INTEGER,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Download queue and history
        conn.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT,
                file_size INTEGER,
                downloaded_size INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                progress REAL DEFAULT 0.0,
                start_time TEXT,
                end_time TEXT,
                speed_kbps REAL,
                error_message TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Allowed domains whitelist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trusted_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE NOT NULL,
                category TEXT,
                trusted INTEGER DEFAULT 1,
                added_at TEXT
            )
        ''')
        
        # File type restrictions
        conn.execute('''
            CREATE TABLE IF NOT EXISTS file_type_restrictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_extension TEXT,
                allowed INTEGER DEFAULT 1,
                created_at TEXT
            )
        ''')
        
        conn.commit()

class URLValidator:
    """Validate and sanitize URLs."""
    
    # Suspicious patterns
    MALICIOUS_PATTERNS = [
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'about:',
        r'file://',
    ]
    
    # Safe domains by default
    SAFE_DOMAINS = {
        'github.com': 'code',
        'gitlab.com': 'code',
        'bitbucket.org': 'code',
        'amazonaws.com': 'cdn',
        'cloudflare.com': 'cdn',
        'google.com': 'search',
        'youtube.com': 'video',
        'wikipedia.org': 'reference',
        'reddit.com': 'social',
        'stackoverflow.com': 'reference',
        'python.org': 'reference',
        'npmjs.com': 'packages',
        'pypi.org': 'packages',
    }
    
    @staticmethod
    def is_valid_url(url: str) -> Tuple[bool, str]:
        """Validate URL format and safety."""
        try:
            # Check for malicious patterns
            url_lower = url.lower()
            for pattern in URLValidator.MALICIOUS_PATTERNS:
                if re.search(pattern, url_lower):
                    return (False, f"Suspicious pattern detected: {pattern}")
            
            # Parse URL
            parsed = urlparse(url)
            
            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return (False, "Invalid URL format - missing scheme or domain")
            
            # Only allow http/https
            if parsed.scheme not in ['http', 'https']:
                return (False, f"Unsupported scheme: {parsed.scheme}")
            
            # Check domain format
            if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', 
                           parsed.netloc):
                return (False, "Invalid domain format")
            
            return (True, "Valid URL")
        
        except Exception as e:
            return (False, f"URL validation error: {str(e)}")
    
    @staticmethod
    def get_domain(url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return ""
    
    @staticmethod
    def is_domain_trusted(domain: str) -> bool:
        """Check if domain is in trusted list."""
        return domain in URLValidator.SAFE_DOMAINS

class FileTypeValidator:
    """Validate file types for download."""
    
    # Allowed file types by default
    SAFE_TYPES = {
        # Documents
        '.pdf': 'document',
        '.txt': 'document',
        '.md': 'document',
        '.doc': 'document',
        '.docx': 'document',
        '.xls': 'document',
        '.xlsx': 'document',
        '.ppt': 'document',
        '.pptx': 'document',
        '.rtf': 'document',
        
        # Archives
        '.zip': 'archive',
        '.tar': 'archive',
        '.tar.gz': 'archive',
        '.rar': 'archive',
        '.7z': 'archive',
        
        # Code/Text
        '.py': 'code',
        '.js': 'code',
        '.json': 'code',
        '.yaml': 'code',
        '.yml': 'code',
        '.xml': 'code',
        '.html': 'code',
        '.css': 'code',
        '.sh': 'code',
        '.ts': 'code',
        '.tsx': 'code',
        '.jsx': 'code',
        '.java': 'code',
        '.cpp': 'code',
        '.c': 'code',
        '.go': 'code',
        '.rb': 'code',
        
        # Media
        '.jpg': 'media',
        '.jpeg': 'media',
        '.png': 'media',
        '.gif': 'media',
        '.webp': 'media',
        '.mp3': 'media',
        '.mp4': 'media',
        '.webm': 'media',
        '.wav': 'media',
        '.mov': 'media',
        '.avi': 'media',
        
        # Data
        '.csv': 'data',
        '.sql': 'data',
        '.sqlite': 'data',
        '.json': 'data',
    }
    
    # Dangerous types
    DANGEROUS_TYPES = [
        '.exe', '.dll', '.so', '.dylib',  # Executables
        '.bat', '.cmd', '.com',            # Scripts
        '.msi', '.app', '.deb', '.rpm',    # Installers
        '.scr', '.vbs', '.ps1',            # Scripts
    ]
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Extract file extension."""
        return os.path.splitext(filename)[1].lower()
    
    @staticmethod
    def is_safe_type(filename: str) -> Tuple[bool, str]:
        """Check if file type is safe for download."""
        ext = FileTypeValidator.get_file_extension(filename)
        
        # Check dangerous types
        if ext in FileTypeValidator.DANGEROUS_TYPES:
            return (False, f"Dangerous file type: {ext}")
        
        # If in safe list, allow
        if ext in FileTypeValidator.SAFE_TYPES:
            return (True, f"Safe type: {FileTypeValidator.SAFE_TYPES[ext]}")
        
        # Unknown types - ask user
        return (False, f"Unknown file type: {ext} - requires approval")
    
    @staticmethod
    def list_safe_types() -> Dict:
        """List all safe file types."""
        return FileTypeValidator.SAFE_TYPES

class BrowserManager:
    """Manage web browser operations and downloads."""
    
    def __init__(self):
        init_browser_db()
        self.downloads = {}  # In-memory download tracking
    
    def log_website_visit(self, user_id: int, url: str, title: str = "", 
                         duration_seconds: int = 0, ip_address: str = "local") -> bool:
        """Log website visit to history."""
        try:
            init_browser_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO browser_history 
                    (user_id, url, title, timestamp, duration_seconds, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, url, title, datetime.utcnow().isoformat(), 
                      duration_seconds, ip_address))
                conn.commit()
            
            logger.info(f"User {user_id} visited: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to log website visit: {e}")
            return False
    
    def get_browser_history(self, user_id: int, hours: int = 24, 
                           limit: int = 50) -> List[Dict]:
        """Get user's browser history."""
        try:
            init_browser_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM browser_history 
                    WHERE user_id = ? AND timestamp > datetime('now', '-' || ? || ' hours')
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (user_id, hours, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get browser history: {e}")
            return []
    
    def queue_download(self, user_id: int, url: str, filename: str = None,
                      custom_path: str = None) -> Tuple[bool, str, Dict]:
        """Queue a file for download."""
        try:
            # Validate URL
            is_valid, msg = URLValidator.is_valid_url(url)
            if not is_valid:
                return (False, f"Invalid URL: {msg}", {})
            
            # Extract filename if not provided
            if not filename:
                filename = url.split('/')[-1] or 'download'
            
            # Validate file type
            is_safe, msg = FileTypeValidator.is_safe_type(filename)
            if not is_safe:
                return (False, f"File type check: {msg}", {})
            
            # Determine download path
            download_path = custom_path or os.path.expanduser("~/Downloads")
            os.makedirs(download_path, exist_ok=True)
            
            full_path = os.path.join(download_path, filename)
            
            # Create download record
            init_browser_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO downloads 
                    (user_id, url, filename, file_path, status, timestamp)
                    VALUES (?, ?, ?, ?, 'queued', ?)
                ''', (user_id, url, filename, full_path, 
                      datetime.utcnow().isoformat()))
                conn.commit()
                
                download_id = conn.execute(
                    'SELECT last_insert_rowid()'
                ).fetchone()[0]
            
            logger.info(f"Download queued: {url} -> {full_path}")
            
            return (True, "Download queued successfully", {
                "download_id": download_id,
                "url": url,
                "filename": filename,
                "path": full_path
            })
        
        except Exception as e:
            logger.error(f"Failed to queue download: {e}")
            return (False, str(e), {})
    
    def get_downloads(self, user_id: int, status: str = None, 
                     limit: int = 50) -> List[Dict]:
        """Get user's downloads."""
        try:
            init_browser_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                
                if status:
                    cursor = conn.execute('''
                        SELECT * FROM downloads 
                        WHERE user_id = ? AND status = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (user_id, status, limit))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM downloads 
                        WHERE user_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (user_id, limit))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get downloads: {e}")
            return []
    
    def update_download_status(self, download_id: int, status: str, 
                              progress: float = 0, speed_kbps: float = 0,
                              file_size: int = 0, error: str = None) -> bool:
        """Update download status."""
        try:
            init_browser_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                end_time = datetime.utcnow().isoformat() if status in ['completed', 'failed'] else None
                
                conn.execute('''
                    UPDATE downloads 
                    SET status = ?, progress = ?, speed_kbps = ?, 
                        file_size = ?, end_time = ?, error_message = ?
                    WHERE id = ?
                ''', (status, progress, speed_kbps, file_size, end_time, error, download_id))
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to update download: {e}")
            return False
    
    def open_website(self, user_id: int, url: str, ip_address: str = "local") -> Dict:
        """Open a website (simulated - actual browser control via other tools)."""
        try:
            # Validate URL
            is_valid, msg = URLValidator.is_valid_url(url)
            if not is_valid:
                return {
                    "status": "error",
                    "message": f"Cannot open website: {msg}",
                    "url": url
                }
            
            domain = URLValidator.get_domain(url)
            
            # Log the visit
            self.log_website_visit(user_id, url, domain, ip_address=ip_address)
            
            return {
                "status": "success",
                "message": f"Website opened: {url}",
                "url": url,
                "domain": domain,
                "trusted": URLValidator.is_domain_trusted(domain),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to open website: {e}")
            return {
                "status": "error",
                "message": str(e),
                "url": url
            }
    
    def get_download_stats(self, user_id: int, hours: int = 24) -> Dict:
        """Get download statistics."""
        try:
            init_browser_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                # Total downloads
                total = conn.execute('''
                    SELECT COUNT(*) FROM downloads 
                    WHERE user_id = ? AND timestamp > datetime('now', '-' || ? || ' hours')
                ''', (user_id, hours)).fetchone()[0]
                
                # Completed
                completed = conn.execute('''
                    SELECT COUNT(*) FROM downloads 
                    WHERE user_id = ? AND status = 'completed'
                    AND timestamp > datetime('now', '-' || ? || ' hours')
                ''', (user_id, hours)).fetchone()[0]
                
                # Failed
                failed = conn.execute('''
                    SELECT COUNT(*) FROM downloads 
                    WHERE user_id = ? AND status = 'failed'
                    AND timestamp > datetime('now', '-' || ? || ' hours')
                ''', (user_id, hours)).fetchone()[0]
                
                # Total size downloaded
                total_size = conn.execute('''
                    SELECT SUM(file_size) FROM downloads 
                    WHERE user_id = ? AND status = 'completed'
                    AND timestamp > datetime('now', '-' || ? || ' hours')
                ''', (user_id, hours)).fetchone()[0] or 0
                
                return {
                    "total_downloads": total,
                    "completed": completed,
                    "failed": failed,
                    "pending": total - completed - failed,
                    "total_size_mb": total_size / (1024 * 1024),
                    "hours": hours
                }
        except Exception as e:
            logger.error(f"Failed to get download stats: {e}")
            return {}

# Global instance
browser_manager = BrowserManager()
