"""Smart Permissions System - Control file access per user."""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

def init_permissions_db():
    """Initialize permissions database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                permission_type TEXT,
                target TEXT,
                allowed INTEGER DEFAULT 0,
                created_at TEXT,
                expires_at TEXT,
                UNIQUE(user_id, permission_type, target)
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

class SmartPermissionManager:
    """Manage per-user, per-file permissions."""
    
    def __init__(self):
        init_permissions_db()
        self.rates = {
            "pdf_read": {"limit": 5, "window_minutes": 10},
            "docx_read": {"limit": 5, "window_minutes": 10},
            "file_read": {"limit": 20, "window_minutes": 10},
        }
    
    def grant_permission(
        self,
        user_id: str,
        permission_type: str,
        target: str,
        duration_hours: int = None
    ) -> bool:
        """Grant permission to user (pdf_read, docx_read, file_read, etc)."""
        try:
            init_permissions_db()
            expires = None
            if duration_hours:
                expires = (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO user_permissions 
                    (user_id, permission_type, target, allowed, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, permission_type, target, 1, datetime.utcnow().isoformat(), expires))
                conn.commit()
            
            logger.info(f"Permission granted: {user_id} -> {permission_type} on {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to grant permission: {e}")
            return False
    
    def deny_permission(self, user_id: str, permission_type: str, target: str) -> bool:
        """Deny permission to user."""
        try:
            init_permissions_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO user_permissions 
                    (user_id, permission_type, target, allowed, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, permission_type, target, 0, datetime.utcnow().isoformat()))
                conn.commit()
            
            logger.info(f"Permission denied: {user_id} -> {permission_type} on {target}")
            return True
        except Exception as e:
            logger.error(f"Failed to deny permission: {e}")
            return False
    
    def has_permission(self, user_id: str, permission_type: str, target: str) -> bool:
        """Check if user has permission for operation."""
        try:
            init_permissions_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute('''
                    SELECT allowed, expires_at FROM user_permissions 
                    WHERE user_id = ? AND permission_type = ? AND target = ?
                ''', (user_id, permission_type, target)).fetchone()
                
                if not row:
                    return False
                
                allowed, expires = row
                
                # Check expiration
                if expires and datetime.fromisoformat(expires) < datetime.utcnow():
                    return False
                
                return bool(allowed)
        except Exception as e:
            logger.error(f"Failed to check permission: {e}")
            return False
    
    def get_user_permissions(self, user_id: str) -> List[Dict]:
        """Get all permissions for user."""
        try:
            init_permissions_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT permission_type, target, allowed, created_at, expires_at 
                    FROM user_permissions 
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                ''', (user_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get user permissions: {e}")
            return []
    
    def revoke_permission(self, user_id: str, permission_type: str = None, target: str = None) -> bool:
        """Revoke all or specific permissions."""
        try:
            init_permissions_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                if permission_type and target:
                    conn.execute('''
                        DELETE FROM user_permissions 
                        WHERE user_id = ? AND permission_type = ? AND target = ?
                    ''', (user_id, permission_type, target))
                else:
                    conn.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Failed to revoke permission: {e}")
            return False
    
    def check_rate_limit(self, user_id: str, operation_type: str) -> Tuple[bool, int]:
        """
        Check if user has exceeded rate limit.
        Returns: (allowed: bool, remaining: int)
        """
        try:
            init_permissions_db()
            
            if operation_type not in self.rates:
                return (True, -1)  # Unknown operation type, allow
            
            limit_config = self.rates[operation_type]
            limit = limit_config["limit"]
            window_minutes = limit_config["window_minutes"]
            
            with sqlite3.connect(DB_PATH) as conn:
                # Count operations in window
                count = conn.execute('''
                    SELECT COUNT(*) as cnt FROM rate_limit_tracking 
                    WHERE user_id = ? AND operation_type = ?
                    AND timestamp > datetime('now', '-' || ? || ' minutes')
                ''', (user_id, operation_type, window_minutes)).fetchone()[0]
                
                remaining = limit - count
                allowed = count < limit
                
                # Log this check
                conn.execute('''
                    INSERT INTO rate_limit_tracking 
                    (user_id, operation_type, timestamp)
                    VALUES (?, ?, ?)
                ''', (user_id, operation_type, datetime.utcnow().isoformat()))
                conn.commit()
                
                return (allowed, max(0, remaining))
        except Exception as e:
            logger.error(f"Failed to check rate limit: {e}")
            return (False, 0)
    
    def get_rate_limit_status(self, user_id: str) -> Dict:
        """Get current rate limit status for all operations."""
        try:
            status = {}
            for op_type in self.rates.keys():
                allowed, remaining = self.check_rate_limit(user_id, op_type)
                limit = self.rates[op_type]["limit"]
                used = limit - remaining
                window = self.rates[op_type]["window_minutes"]
                
                status[op_type] = {
                    "allowed": allowed,
                    "used": used,
                    "limit": limit,
                    "remaining": remaining,
                    "window_minutes": window
                }
            return status
        except Exception as e:
            logger.error(f"Failed to get rate limit status: {e}")
            return {}
    
    def set_rate_limit(self, operation_type: str, limit: int, window_minutes: int):
        """Configure rate limits."""
        self.rates[operation_type] = {
            "limit": limit,
            "window_minutes": window_minutes
        }
        logger.info(f"Rate limit updated: {operation_type} = {limit}/{window_minutes}min")

# Global instance
permission_manager = SmartPermissionManager()
