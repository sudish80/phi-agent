"""User Mode System - Private, Guest, Incognito modes."""

import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

class ModeManager:
    """Manage user modes (normal, private, guest, incognito)."""
    
    AVAILABLE_MODES = {
        "normal": {
            "name": "Normal",
            "description": "Standard operation with full logging",
            "log_access": True,
            "store_history": True,
            "require_approval": False,
            "timeout_minutes": 480  # 8 hours
        },
        "private": {
            "name": "Private",
            "description": "Personal use with selective logging",
            "log_access": True,
            "store_history": False,
            "require_approval": True,
            "timeout_minutes": 120  # 2 hours
        },
        "guest": {
            "name": "Guest",
            "description": "Limited access, minimal permissions",
            "log_access": True,
            "store_history": False,
            "require_approval": True,
            "timeout_minutes": 60  # 1 hour
        },
        "incognito": {
            "name": "Incognito",
            "description": "Maximum privacy, minimal logging",
            "log_access": False,
            "store_history": False,
            "require_approval": False,
            "timeout_minutes": 30  # 30 minutes
        }
    }
    
    def __init__(self):
        self._init_modes_table()
    
    def _init_modes_table(self):
        """Initialize modes table."""
        with sqlite3.connect(DB_PATH) as conn:
            # Use the same schema as in auth_manager
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_modes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT,
                    expires_at TEXT,
                    preferences TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.commit()
    
    def set_mode(self, user_id: int, mode: str, duration_minutes: int = None) -> Tuple[bool, str]:
        """Set user mode (normal, private, guest, incognito)."""
        if mode not in self.AVAILABLE_MODES:
            return (False, f"Invalid mode. Available: {list(self.AVAILABLE_MODES.keys())}")
        
        try:
            duration = duration_minutes or self.AVAILABLE_MODES[mode]["timeout_minutes"]
            expires_at = datetime.utcnow() + timedelta(minutes=duration)
            
            with sqlite3.connect(DB_PATH) as conn:
                # Clear other active modes
                conn.execute(
                    "UPDATE user_modes SET enabled = 0 WHERE user_id = ? AND enabled = 1",
                    (user_id,)
                )
                
                # Set new mode
                conn.execute('''
                    INSERT INTO user_modes 
                    (user_id, mode, enabled, created_at, expires_at)
                    VALUES (?, ?, 1, ?, ?)
                ''', (user_id, mode, datetime.utcnow().isoformat(), expires_at.isoformat()))
                
                conn.commit()
            
            mode_info = self.AVAILABLE_MODES[mode]
            logger.info(f"User {user_id} switched to {mode} mode")
            
            return (True, f"Switched to {mode_info['name']} mode: {mode_info['description']}")
        
        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            return (False, str(e))
    
    def get_current_mode(self, user_id: int) -> Dict:
        """Get current user mode."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                mode_row = conn.execute('''
                    SELECT mode, expires_at FROM user_modes 
                    WHERE user_id = ? AND enabled = 1
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_id,)).fetchone()
                
                if not mode_row:
                    mode = "normal"
                else:
                    mode = mode_row[0]
                    # Check expiration
                    expires = datetime.fromisoformat(mode_row[1])
                    if expires < datetime.utcnow():
                        conn.execute(
                            "UPDATE user_modes SET enabled = 0 WHERE user_id = ? AND mode = ?",
                            (user_id, mode)
                        )
                        conn.commit()
                        mode = "normal"
                
                return {
                    "mode": mode,
                    "info": self.AVAILABLE_MODES[mode],
                    "expires_at": mode_row[1] if mode_row else None
                }
        
        except Exception as e:
            logger.error(f"Error getting mode: {e}")
            return {"mode": "normal", "info": self.AVAILABLE_MODES["normal"]}
    
    def get_mode_settings(self, mode: str) -> Dict:
        """Get settings for a specific mode."""
        if mode in self.AVAILABLE_MODES:
            return self.AVAILABLE_MODES[mode]
        return {}
    
    def list_available_modes(self) -> Dict:
        """List all available modes."""
        return {
            mode: info for mode, info in self.AVAILABLE_MODES.items()
        }
    
    def exit_mode(self, user_id: int) -> Tuple[bool, str]:
        """Exit current mode and return to normal."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE user_modes SET enabled = 0 WHERE user_id = ? AND enabled = 1",
                    (user_id,)
                )
                conn.commit()
            
            logger.info(f"User {user_id} exited special mode")
            return (True, "Returned to normal mode")
        
        except Exception as e:
            logger.error(f"Error exiting mode: {e}")
            return (False, str(e))

# Global instance
mode_manager = ModeManager()
