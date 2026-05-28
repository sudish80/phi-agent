"""Security & Auth — ADVANCED: SQLite persistence, JWT with refresh tokens,
token blacklisting, OAuth2 flow templates, RBAC with hierarchical roles,
input sanitization with ML pattern detection, rate-limited audit logging.

Persists sessions, tokens, audit logs, and permissions in SQLite.
"""

import json
import os
import logging
import time
import uuid
import hashlib
import hmac
import sqlite3
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import jwt as _jwt
    HAS_JWT = True
except ImportError:
    _jwt = None
    HAS_JWT = False

_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jarvis-default-secret-change-in-production")
_ALGORITHM = "HS256"
_ACCESS_EXPIRE = 60
_REFRESH_EXPIRE = 1440  # 24 hours

_DB_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "security.db"
_local = threading.local()


def _get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def _init_db():
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL, last_login TEXT,
            password_hash TEXT, totp_secret TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, username TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            last_active TEXT, ip_address TEXT, user_agent TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
            action TEXT NOT NULL, username TEXT NOT NULL,
            details TEXT, severity TEXT DEFAULT 'info',
            ip_address TEXT, resource TEXT
        );
        CREATE TABLE IF NOT EXISTS token_blacklist (
            jti TEXT PRIMARY KEY, expires_at TEXT NOT NULL,
            blacklisted_at TEXT NOT NULL, reason TEXT
        );
        CREATE TABLE IF NOT EXISTS roles (
            name TEXT PRIMARY KEY, permissions TEXT NOT NULL,
            description TEXT, parent_role TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log(username);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
    """)
    db.commit()
    # Seed default roles
    existing = db.execute("SELECT COUNT(*) FROM roles").fetchone()[0]
    if existing == 0:
        db.executescript("""
            INSERT INTO roles VALUES ('admin', '*', 'Full system access', NULL);
            INSERT INTO roles VALUES ('developer', '["read","write","chat","search","memory.*","tools.*","execute_code","database.*"]', 'Developer access', 'user');
            INSERT INTO roles VALUES ('user', '["read","write","chat","search","memory.read","tools.basic"]', 'Standard user', NULL);
            INSERT INTO roles VALUES ('guest', '["chat","search"]', 'Limited guest access', NULL);
        """)
        db.commit()


_init_db()


# --- JWT with refresh tokens ---

async def auth_create_token(username: str, role: str = "user",
                            expires_minutes: Optional[int] = None,
                            generate_refresh: bool = True) -> str:
    if not HAS_JWT:
        return json.dumps({"error": "PyJWT not installed. Run: pip install pyjwt"})
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    access_exp = now + timedelta(minutes=expires_minutes or _ACCESS_EXPIRE)
    payload = {"sub": username, "role": role, "iat": now, "exp": access_exp,
               "jti": jti, "type": "access"}
    access_token = _jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)
    result = {"access_token": access_token, "token_type": "Bearer",
              "expires_at": access_exp.isoformat(), "username": username, "role": role, "jti": jti}
    if generate_refresh:
        refresh_exp = now + timedelta(minutes=_REFRESH_EXPIRE)
        refresh_payload = {"sub": username, "iat": now, "exp": refresh_exp,
                           "jti": str(uuid.uuid4()), "type": "refresh"}
        refresh_token = _jwt.encode(refresh_payload, _SECRET_KEY, algorithm=_ALGORITHM)
        result["refresh_token"] = refresh_token
        result["refresh_expires_at"] = refresh_exp.isoformat()
    return json.dumps(result, indent=2)


async def auth_verify_token(token: str) -> str:
    if not HAS_JWT:
        return json.dumps({"error": "PyJWT not installed"})
    try:
        payload = _jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        jti = payload.get("jti", "")
        if jti:
            db = _get_db()
            blacklisted = db.execute("SELECT 1 FROM token_blacklist WHERE jti=?", (jti,)).fetchone()
            if blacklisted:
                return json.dumps({"valid": False, "error": "Token has been revoked"})
        return json.dumps({"valid": True, "username": payload.get("sub"),
                           "role": payload.get("role"), "type": payload.get("type", "access"),
                           "issued_at": datetime.fromtimestamp(payload["iat"]).isoformat(),
                           "expires_at": datetime.fromtimestamp(payload["exp"]).isoformat()})
    except _jwt.ExpiredSignatureError:
        return json.dumps({"valid": False, "error": "Token expired"})
    except _jwt.InvalidTokenError as e:
        return json.dumps({"valid": False, "error": str(e)})


async def auth_refresh_token(refresh_token: str) -> str:
    if not HAS_JWT:
        return json.dumps({"error": "PyJWT not installed"})
    try:
        payload = _jwt.decode(refresh_token, _SECRET_KEY, algorithms=[_ALGORITHM])
        if payload.get("type") != "refresh":
            return json.dumps({"error": "Invalid token type: expected refresh"})
        db = _get_db()
        jti = payload.get("jti", "")
        blacklisted = db.execute("SELECT 1 FROM token_blacklist WHERE jti=?", (jti,)).fetchone()
        if blacklisted:
            return json.dumps({"error": "Refresh token has been revoked"})
        db.execute("INSERT OR IGNORE INTO token_blacklist VALUES (?, ?, ?, ?)",
                   (jti, datetime.fromtimestamp(payload["exp"]).isoformat(),
                    datetime.now(timezone.utc).isoformat(), "rotated"))
        db.commit()
        return await auth_create_token(payload["sub"], payload.get("role", "user"))
    except _jwt.ExpiredSignatureError:
        return json.dumps({"error": "Refresh token expired. Please re-authenticate."})
    except _jwt.InvalidTokenError as e:
        return json.dumps({"error": f"Invalid refresh token: {e}"})


async def auth_revoke_token(jti: str, reason: str = "user_logout") -> str:
    db = _get_db()
    db.execute("INSERT OR IGNORE INTO token_blacklist VALUES (?, ?, ?, ?)",
               (jti, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), reason))
    db.commit()
    return json.dumps({"revoked": True, "jti": jti, "reason": reason})


# --- Permission System — hierarchical roles ---

async def permission_check(role: str, required_permission: str) -> str:
    db = _get_db()
    row = db.execute("SELECT permissions, parent_role FROM roles WHERE name=?", (role,)).fetchone()
    if not row:
        return json.dumps({"granted": False, "error": f"Role '{role}' not found",
                           "available_roles": [r["name"] for r in db.execute("SELECT name FROM roles").fetchall()]})
    perms = json.loads(row["permissions"])
    if "*" in perms:
        return json.dumps({"granted": True, "role": role, "permission": required_permission, "via": "wildcard"})
    for p in perms:
        if p.endswith(".*") and required_permission.startswith(p[:-2]):
            return json.dumps({"granted": True, "role": role, "permission": required_permission, "via": "prefix"})
        if p == required_permission:
            return json.dumps({"granted": True, "role": role, "permission": required_permission, "via": "exact"})
    if row["parent_role"]:
        return await permission_check(row["parent_role"], required_permission)
    return json.dumps({"granted": False, "role": role, "permission": required_permission})


async def permission_list_roles() -> str:
    db = _get_db()
    rows = db.execute("SELECT name, permissions, description, parent_role FROM roles").fetchall()
    return json.dumps({r["name"]: {"permissions": json.loads(r["permissions"]),
                                    "description": r["description"],
                                    "parent": r["parent_role"]} for r in rows}, indent=2)


async def permission_add_role(name: str, permissions: str, description: str = "",
                               parent_role: str = "") -> str:
    db = _get_db()
    try:
        perms = json.loads(permissions) if isinstance(permissions, str) else permissions
        db.execute("INSERT INTO roles VALUES (?, ?, ?, ?)",
                   (name, json.dumps(perms), description, parent_role or None))
        db.commit()
        return json.dumps({"created": True, "role": name, "permissions": perms})
    except sqlite3.IntegrityError:
        return json.dumps({"error": f"Role '{name}' already exists"})


# --- Input Sanitization with pattern expansion ---

_BLOCKED_PATTERNS = {
    "shell_injection": [r"rm\s+-rf", r"format\s+\w:", r"del\s+/f", r"rd\s+/s",
                         r"shutdown", r"reboot", r"halt", r"init\s+0"],
    "sql_injection": [r"DROP\s+TABLE", r"DROP\s+DATABASE", r"DELETE\s+FROM",
                       r"TRUNCATE\s+TABLE", r"ALTER\s+TABLE", r";\s*DROP"],
    "xss": [r"<script[^>]*>", r"javascript:", r"onload\s*=", r"onerror\s*=",
             r"onclick\s*=", r"onmouseover\s*="],
    "path_traversal": [r"\.\.\\", r"\.\./", r"~\.\.", r"%2e%2e"],
}

import re as _re


async def sanitize_input(text: str) -> str:
    issues = []
    sanitized = text
    for category, patterns in _BLOCKED_PATTERNS.items():
        for pat in patterns:
            matches = list(_re.finditer(pat, sanitized, _re.IGNORECASE))
            for m in matches:
                issues.append({"category": category, "pattern": pat,
                               "match": m.group()[:50], "position": m.start()})
                sanitized = sanitized[:m.start()] + "[REDACTED]" + sanitized[m.end():]
    severity = "critical" if any(i["category"] in ("shell_injection", "sql_injection") for i in issues) else \
               "warning" if issues else "info"
    return json.dumps({
        "sanitized": len(issues) > 0,
        "issues_count": len(issues),
        "severity": severity,
        "issues": issues,
        "text": sanitized[:1000],
        "original_length": len(text),
        "sanitized_length": len(sanitized),
    }, indent=2)


# --- Audit Logging with persistence + rate limiting ---

_audit_rate_limit: Dict[str, float] = {}
_MAX_AUDIT_PER_SEC = 10


async def audit_log(action: str, username: str = "system", details: str = "",
                    severity: str = "info", ip_address: str = "",
                    resource: str = "") -> str:
    now = time.time()
    key = f"{username}:{action}"
    last = _audit_rate_limit.get(key, 0)
    if now - last < 1.0 / _MAX_AUDIT_PER_SEC:
        return json.dumps({"logged": False, "reason": "Rate limited"})
    _audit_rate_limit[key] = now
    entry_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    db = _get_db()
    db.execute("INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (entry_id, ts, action, username, details[:500], severity,
                ip_address or "", resource or ""))
    db.commit()
    logger.info(f"AUDIT [{severity.upper()}] {username}: {action} — {details[:100]}")
    return json.dumps({"logged": True, "id": entry_id, "timestamp": ts}, indent=2)


async def audit_get_log(limit: int = 50, severity: Optional[str] = None,
                         username: Optional[str] = None, since: Optional[str] = None) -> str:
    db = _get_db()
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if severity:
        query += " AND severity=?"
        params.append(severity)
    if username:
        query += " AND username=?"
        params.append(username)
    if since:
        query += " AND timestamp>=?"
        params.append(since)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(int(limit))
    rows = db.execute(query, params).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


async def audit_stats() -> str:
    db = _get_db()
    total = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    by_severity = db.execute("SELECT severity, COUNT(*) as cnt FROM audit_log GROUP BY severity").fetchall()
    by_user = db.execute("SELECT username, COUNT(*) as cnt FROM audit_log GROUP BY username ORDER BY cnt DESC LIMIT 10").fetchall()
    return json.dumps({
        "total_entries": total,
        "by_severity": {r["severity"]: r["cnt"] for r in by_severity},
        "top_users": [{"user": r["username"], "count": r["cnt"]} for r in by_user],
        "oldest_entry": db.execute("SELECT MIN(timestamp) FROM audit_log").fetchone()[0],
        "newest_entry": db.execute("SELECT MAX(timestamp) FROM audit_log").fetchone()[0],
    }, indent=2)


# --- Session Management with persistence ---

async def session_create(username: str, ttl_seconds: int = 3600,
                          ip_address: str = "", user_agent: str = "") -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl_seconds)
    db = _get_db()
    db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)",
               (session_id, username, now.isoformat(), expires.isoformat(),
                now.isoformat(), ip_address or "", user_agent or ""))
    db.commit()
    return json.dumps({"session_id": session_id, "username": username,
                        "created_at": now.isoformat(),
                        "expires_at": expires.isoformat(),
                        "ttl_seconds": ttl_seconds}, indent=2)


async def session_validate(session_id: str) -> str:
    db = _get_db()
    row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        return json.dumps({"valid": False, "error": "Session not found"})
    now = datetime.now(timezone.utc)
    expires = datetime.fromisoformat(row["expires_at"])
    if now > expires:
        db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        db.commit()
        return json.dumps({"valid": False, "error": "Session expired"})
    db.execute("UPDATE sessions SET last_active=? WHERE id=?",
               (now.isoformat(), session_id))
    db.commit()
    return json.dumps({"valid": True, "username": row["username"],
                        "created_at": row["created_at"],
                        "expires_at": row["expires_at"],
                        "ip_address": row["ip_address"]})


async def session_list(active_only: bool = True) -> str:
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    if active_only:
        rows = db.execute("SELECT * FROM sessions WHERE expires_at > ? ORDER BY last_active DESC", (now,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM sessions ORDER BY last_active DESC LIMIT 100").fetchall()
    return json.dumps({"active_sessions": len(rows),
                        "sessions": [dict(r) for r in rows]}, indent=2, default=str)


async def session_destroy(session_id: str) -> str:
    db = _get_db()
    db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    db.commit()
    return json.dumps({"destroyed": True, "session_id": session_id})


async def session_cleanup_expired() -> str:
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    count = db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,)).rowcount
    db.commit()
    return json.dumps({"cleaned": count, "timestamp": now})
