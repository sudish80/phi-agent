import hashlib
import hmac
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEntry:
    count: int = 0
    window_start: float = 0.0


class RateLimiter:
    def __init__(self, max_calls: int = 100, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._lock = Lock()

    def check(self, session_id: str) -> bool:
        now = time.time()
        with self._lock:
            entry = self._entries[session_id]
            if now - entry.window_start > self.window_seconds:
                entry.count = 0
                entry.window_start = now
            entry.count += 1
            allowed = entry.count <= self.max_calls
            if not allowed:
                logger.warning("Rate limit exceeded for session %s", session_id)
            return allowed

    def remaining(self, session_id: str) -> int:
        now = time.time()
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is None:
                return self.max_calls
            if now - entry.window_start > self.window_seconds:
                return self.max_calls
            return max(0, self.max_calls - entry.count)

    def reset(self, session_id: str):
        with self._lock:
            self._entries.pop(session_id, None)


class TokenValidator:
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or "default-secret-key-change-in-production"
        self._valid_api_keys: dict[str, dict] = {}
        self._lock = Lock()

    def register_api_key(self, key: str, metadata: dict = None):
        with self._lock:
            self._valid_api_keys[key] = metadata or {}

    def revoke_api_key(self, key: str):
        with self._lock:
            self._valid_api_keys.pop(key, None)

    def validate_api_key(self, token: str) -> tuple[bool, Optional[dict]]:
        with self._lock:
            metadata = self._valid_api_keys.get(token)
            if metadata is not None:
                return True, metadata
        return False, None

    def generate_jwt(self, payload: dict, expiry_hours: int = 24) -> str:
        import jwt as pyjwt
        payload = payload.copy()
        payload["iat"] = int(time.time())
        payload["exp"] = int(time.time()) + expiry_hours * 3600
        return pyjwt.encode(payload, self.secret_key, algorithm="HS256")

    def validate_jwt(self, token: str) -> tuple[bool, Optional[dict]]:
        import jwt as pyjwt
        try:
            payload = pyjwt.decode(token, self.secret_key, algorithms=["HS256"])
            return True, payload
        except pyjwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return False, None
        except pyjwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token: %s", e)
            return False, None

    def validate(self, token: str) -> tuple[bool, Optional[dict]]:
        is_valid, data = self.validate_api_key(token)
        if is_valid:
            return True, data
        return self.validate_jwt(token)


class SessionScoper:
    def __init__(self):
        self._session_scopes: dict[str, set[str]] = {}
        self._tool_grants: dict[str, set[str]] = {}
        self._lock = Lock()

    def set_scope(self, session_id: str, allowed_tools: list[str]):
        with self._lock:
            self._session_scopes[session_id] = set(allowed_tools)

    def add_tool_to_scope(self, session_id: str, tool_name: str):
        with self._lock:
            if session_id not in self._session_scopes:
                self._session_scopes[session_id] = set()
            self._session_scopes[session_id].add(tool_name)

    def remove_tool_from_scope(self, session_id: str, tool_name: str):
        with self._lock:
            if session_id in self._session_scopes:
                self._session_scopes[session_id].discard(tool_name)

    def is_tool_allowed(self, session_id: str, tool_name: str) -> bool:
        with self._lock:
            scopes = self._session_scopes.get(session_id)
            if scopes is None:
                return True
            return tool_name in scopes

    def get_scope(self, session_id: str) -> list[str]:
        with self._lock:
            scopes = self._session_scopes.get(session_id)
            return list(scopes) if scopes else []

    def clear_scope(self, session_id: str):
        with self._lock:
            self._session_scopes.pop(session_id, None)

    def grant_tool(self, tool_name: str, session_id: str):
        with self._lock:
            if tool_name not in self._tool_grants:
                self._tool_grants[tool_name] = set()
            self._tool_grants[tool_name].add(session_id)

    def revoke_tool(self, tool_name: str, session_id: str):
        with self._lock:
            if tool_name in self._tool_grants:
                self._tool_grants[tool_name].discard(session_id)


class SecurityManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.rate_limiter = RateLimiter()
                    cls._instance.token_validator = TokenValidator()
                    cls._instance.session_scoper = SessionScoper()
        return cls._instance

    def authorize_request(self, session_id: str, token: str, tool_name: str) -> tuple[bool, str]:
        valid, data = self.token_validator.validate(token)
        if not valid:
            return False, "Invalid or expired token"

        if not self.session_scoper.is_tool_allowed(session_id, tool_name):
            return False, f"Tool '{tool_name}' not allowed for this session"

        if not self.rate_limiter.check(session_id):
            return False, "Rate limit exceeded"

        return True, "Authorized"

    def get_status(self, session_id: str) -> dict:
        return {
            "session_id": session_id,
            "rate_limit_remaining": self.rate_limiter.remaining(session_id),
            "scope": self.session_scoper.get_scope(session_id),
        }
