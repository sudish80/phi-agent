"""User Authentication and Session Management System."""

import sqlite3
import hashlib
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging
import secrets

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'phi_audit.db')

def init_auth_db():
    """Initialize authentication database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Users table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active INTEGER DEFAULT 1,
                preferences TEXT
            )
        ''')
        
        # Sessions table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                mode TEXT DEFAULT 'normal',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # User modes table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                enabled INTEGER DEFAULT 0,
                created_at TEXT,
                expires_at TEXT,
                preferences TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()

def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

class AuthManager:
    """Manage user authentication and sessions."""
    
    def __init__(self):
        init_auth_db()
    
    def signup(self, username: str, email: str, password: str) -> Tuple[bool, str, Dict]:
        """Register new user."""
        try:
            init_auth_db()
            
            if len(password) < 8:
                return (False, "Password must be at least 8 characters", {})
            
            if len(username) < 3:
                return (False, "Username must be at least 3 characters", {})
            
            with sqlite3.connect(DB_PATH) as conn:
                # Check if user exists
                existing = conn.execute(
                    "SELECT id FROM users WHERE username = ? OR email = ?",
                    (username, email)
                ).fetchone()
                
                if existing:
                    return (False, "Username or email already exists", {})
                
                # Create user
                password_hash = hash_password(password)
                conn.execute('''
                    INSERT INTO users (username, email, password_hash, created_at, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (username, email, password_hash, datetime.utcnow().isoformat()))
                conn.commit()
                
                user = conn.execute("SELECT id, username FROM users WHERE username = ?", 
                                   (username,)).fetchone()
            
            logger.info(f"New user registered: {username}")
            return (True, "User created successfully", {"user_id": user[0], "username": user[1]})
        
        except Exception as e:
            logger.error(f"Signup error: {e}")
            return (False, f"Signup failed: {str(e)}", {})
    
    def login(self, username: str, password: str, ip_address: str = "unknown") -> Tuple[bool, str, Dict]:
        """Authenticate user and create session."""
        try:
            init_auth_db()
            password_hash = hash_password(password)
            
            with sqlite3.connect(DB_PATH) as conn:
                user = conn.execute('''
                    SELECT id, username, password_hash, is_active FROM users 
                    WHERE username = ?
                ''', (username,)).fetchone()
                
                if not user:
                    logger.warning(f"Login attempt for non-existent user: {username}")
                    return (False, "Invalid username or password", {})
                
                user_id, uname, stored_hash, is_active = user
                
                if not is_active:
                    return (False, "Account is disabled", {})
                
                if stored_hash != password_hash:
                    logger.warning(f"Failed login attempt for user: {username}")
                    return (False, "Invalid username or password", {})
                
                # Create session
                session_token = secrets.token_urlsafe(32)
                expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
                
                conn.execute('''
                    INSERT INTO sessions 
                    (user_id, session_token, created_at, expires_at, ip_address, mode)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, session_token, datetime.utcnow().isoformat(), expires_at, ip_address, "normal"))
                
                # Update last login
                conn.execute('''
                    UPDATE users SET last_login = ? WHERE id = ?
                ''', (datetime.utcnow().isoformat(), user_id))
                
                conn.commit()
            
            logger.info(f"User logged in: {username}")
            return (True, "Login successful", {
                "user_id": user_id,
                "username": uname,
                "session_token": session_token,
                "expires_at": expires_at
            })
        
        except Exception as e:
            logger.error(f"Login error: {e}")
            return (False, f"Login failed: {str(e)}", {})
    
    def verify_session(self, session_token: str) -> Tuple[bool, int, str]:
        """Verify session token. Returns (is_valid, user_id, username)."""
        try:
            init_auth_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                session = conn.execute('''
                    SELECT s.user_id, u.username, s.expires_at FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.session_token = ? AND u.is_active = 1
                ''', (session_token,)).fetchone()
                
                if not session:
                    return (False, 0, "")
                
                user_id, username, expires_at = session
                
                # Check expiration
                if datetime.fromisoformat(expires_at) < datetime.utcnow():
                    return (False, 0, "")
                
                return (True, user_id, username)
        
        except Exception as e:
            logger.error(f"Session verification error: {e}")
            return (False, 0, "")
    
    def logout(self, session_token: str) -> bool:
        """Logout user by invalidating session."""
        try:
            init_auth_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
                conn.commit()
            
            logger.info("User logged out")
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    def get_session_info(self, session_token: str) -> Dict:
        """Get session information."""
        try:
            init_auth_db()
            
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                session = conn.execute('''
                    SELECT s.user_id, u.username, s.mode, s.created_at, s.expires_at, s.ip_address
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.session_token = ?
                ''', (session_token,)).fetchone()
                
                if session:
                    return dict(session)
                return {}
        except Exception as e:
            logger.error(f"Get session info error: {e}")
            return {}
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password."""
        try:
            init_auth_db()
            
            if len(new_password) < 8:
                return (False, "New password must be at least 8 characters")
            
            with sqlite3.connect(DB_PATH) as conn:
                user = conn.execute(
                    "SELECT password_hash FROM users WHERE id = ?",
                    (user_id,)
                ).fetchone()
                
                if not user:
                    return (False, "User not found")
                
                old_hash = hash_password(old_password)
                if user[0] != old_hash:
                    return (False, "Current password is incorrect")
                
                new_hash = hash_password(new_password)
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (new_hash, user_id)
                )
                conn.commit()
            
            logger.info(f"Password changed for user ID: {user_id}")
            return (True, "Password changed successfully")
        
        except Exception as e:
            logger.error(f"Change password error: {e}")
            return (False, f"Failed to change password: {str(e)}")

# Global instance
auth_manager = AuthManager()
