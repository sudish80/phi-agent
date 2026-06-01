"""Audit Logging System - Track all file operations and access."""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

def init_audit_db():
    """Initialize audit logging database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS file_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                file_path TEXT NOT NULL,
                operation TEXT NOT NULL,
                file_type TEXT,
                file_size INTEGER,
                status TEXT,
                summary TEXT,
                approved_by_user INTEGER DEFAULT 0,
                extracted_size INTEGER,
                error_message TEXT,
                ip_address TEXT,
                metadata TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                permission_type TEXT,
                file_path TEXT,
                file_type TEXT,
                allowed INTEGER DEFAULT 0,
                created_at TEXT,
                expires_at TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS rate_limit_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                operation_type TEXT,
                timestamp TEXT NOT NULL,
                file_path TEXT
            )
        ''')
        
        conn.commit()

def log_file_access(
    user_id: str = "unknown",
    file_path: str = "",
    operation: str = "",
    file_type: str = "",
    file_size: int = 0,
    status: str = "success",
    summary: str = "",
    approved: int = 0,
    extracted_size: int = 0,
    error: str = "",
    ip_address: str = "local",
    metadata: Dict = None
) -> bool:
    """Log file access operation to audit database."""
    try:
        init_audit_db()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO file_access_log 
                (timestamp, user_id, file_path, operation, file_type, file_size, 
                 status, summary, approved_by_user, extracted_size, error_message, 
                 ip_address, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.utcnow().isoformat(),
                user_id,
                file_path,
                operation,
                file_type,
                file_size,
                status,
                summary,
                approved,
                extracted_size,
                error,
                ip_address,
                json.dumps(metadata or {})
            ))
            conn.commit()
        
        return True
    except Exception as e:
        logger.error(f"Failed to log file access: {e}")
        return False

def get_audit_log(
    user_id: str = None,
    hours: int = 24,
    limit: int = 100
) -> List[Dict]:
    """Retrieve audit logs."""
    try:
        init_audit_db()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM file_access_log WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " AND timestamp > datetime('now', '-' || ? || ' hours')"
            params.append(hours)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            logs = [dict(row) for row in cursor.fetchall()]
            
        return logs
    except Exception as e:
        logger.error(f"Failed to retrieve audit logs: {e}")
        return []

def get_user_stats(user_id: str, hours: int = 24) -> Dict:
    """Get file access statistics for user."""
    try:
        init_audit_db()
        
        with sqlite3.connect(DB_PATH) as conn:
            # Total accesses
            total = conn.execute('''
                SELECT COUNT(*) as count FROM file_access_log 
                WHERE user_id = ? AND timestamp > datetime('now', '-' || ? || ' hours')
            ''', (user_id, hours)).fetchone()[0]
            
            # Successful vs denied
            approved = conn.execute('''
                SELECT COUNT(*) as count FROM file_access_log 
                WHERE user_id = ? AND approved_by_user = 1 
                AND timestamp > datetime('now', '-' || ? || ' hours')
            ''', (user_id, hours)).fetchone()[0]
            
            denied = conn.execute('''
                SELECT COUNT(*) as count FROM file_access_log 
                WHERE user_id = ? AND status = 'denied'
                AND timestamp > datetime('now', '-' || ? || ' hours')
            ''', (user_id, hours)).fetchone()[0]
            
            # Data extracted
            data_size = conn.execute('''
                SELECT SUM(extracted_size) as total FROM file_access_log 
                WHERE user_id = ? AND status = 'success'
                AND timestamp > datetime('now', '-' || ? || ' hours')
            ''', (user_id, hours)).fetchone()[0] or 0
            
            # File types accessed
            file_types = conn.execute('''
                SELECT file_type, COUNT(*) as count FROM file_access_log 
                WHERE user_id = ? AND timestamp > datetime('now', '-' || ? || ' hours')
                GROUP BY file_type
            ''', (user_id, hours)).fetchall()
            
        return {
            "total_accesses": total,
            "approved": approved,
            "denied": denied,
            "data_extracted_kb": data_size / 1024,
            "file_types": [{"type": ft[0], "count": ft[1]} for ft in file_types]
        }
    except Exception as e:
        logger.error(f"Failed to get user stats: {e}")
        return {}

def export_audit_log_json(user_id: str = None, hours: int = 24) -> str:
    """Export audit logs as JSON."""
    logs = get_audit_log(user_id, hours, limit=1000)
    return json.dumps(logs, indent=2, default=str)

def clear_old_logs(days: int = 90):
    """Clear audit logs older than specified days."""
    try:
        init_audit_db()
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                DELETE FROM file_access_log 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            ''', (days,))
            conn.commit()
        
        return True
    except Exception as e:
        logger.error(f"Failed to clear old logs: {e}")
        return False
