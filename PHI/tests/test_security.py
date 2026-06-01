import time
import json
import tempfile
import pytest
from unittest.mock import patch
from backend.security.session_security import (
    RateLimiter,
    TokenValidator,
    SessionScoper,
    SecurityManager,
)
from backend.security.audit import AuditStore, AuditEntry, log_action


class TestRateLimiter:
    @pytest.fixture
    def limiter(self):
        return RateLimiter(max_calls=5, window_seconds=60)

    def test_allow_within_limit(self, limiter):
        for _ in range(5):
            assert limiter.check("sess_1") is True

    def test_block_after_threshold(self, limiter):
        for _ in range(5):
            limiter.check("sess_2")
        assert limiter.check("sess_2") is False

    def test_different_sessions_independent(self, limiter):
        for _ in range(5):
            limiter.check("busy")
        assert limiter.check("other") is True

    def test_window_resets(self, limiter):
        limiter.window_seconds = 0.1
        for _ in range(5):
            limiter.check("sess_r")
        time.sleep(0.15)
        assert limiter.check("sess_r") is True

    def test_remaining_counts(self, limiter):
        assert limiter.remaining("fresh") == 5
        limiter.check("fresh")
        assert limiter.remaining("fresh") == 4

    def test_remaining_after_block(self, limiter):
        for _ in range(5):
            limiter.check("sess_full")
        assert limiter.remaining("sess_full") == 0

    def test_remaining_after_window_expires(self, limiter):
        limiter.window_seconds = 0.1
        limiter.check("sess_t")
        time.sleep(0.15)
        assert limiter.remaining("sess_t") == 5

    def test_reset(self, limiter):
        for _ in range(5):
            limiter.check("sess_rst")
        limiter.reset("sess_rst")
        assert limiter.remaining("sess_rst") == 5


class TestTokenValidator:
    @pytest.fixture
    def validator(self):
        v = TokenValidator(secret_key="test-secret")
        v.register_api_key("valid-key-123", {"role": "admin"})
        return v

    def test_valid_api_key(self, validator):
        valid, data = validator.validate_api_key("valid-key-123")
        assert valid is True
        assert data == {"role": "admin"}

    def test_invalid_api_key(self, validator):
        valid, _ = validator.validate_api_key("bad-key")
        assert valid is False

    def test_revoke_api_key(self, validator):
        validator.revoke_api_key("valid-key-123")
        valid, _ = validator.validate_api_key("valid-key-123")
        assert valid is False

    def test_validate_delegates_to_api_key(self, validator):
        valid, data = validator.validate("valid-key-123")
        assert valid is True

    def test_validate_delegates_to_jwt(self, validator):
        token = validator.generate_jwt({"sub": "user1"}, expiry_hours=1)
        valid, payload = validator.validate(token)
        assert valid is True
        assert payload["sub"] == "user1"

    def test_expired_jwt(self, validator):
        token = validator.generate_jwt({"sub": "user1"}, expiry_hours=0)
        time.sleep(0.05)
        valid, _ = validator.validate(token)
        assert valid is False


class TestSessionScoper:
    @pytest.fixture
    def scoper(self):
        return SessionScoper()

    def test_no_scope_allows_all(self, scoper):
        assert scoper.is_tool_allowed("sess_1", "any_tool") is True

    def test_set_scope_restricts_tools(self, scoper):
        scoper.set_scope("sess_r", ["chat", "read"])
        assert scoper.is_tool_allowed("sess_r", "chat") is True
        assert scoper.is_tool_allowed("sess_r", "delete") is False

    def test_add_tool_to_scope(self, scoper):
        scoper.set_scope("sess_a", ["chat"])
        scoper.add_tool_to_scope("sess_a", "search")
        assert scoper.is_tool_allowed("sess_a", "search") is True

    def test_remove_tool_from_scope(self, scoper):
        scoper.set_scope("sess_b", ["chat", "write"])
        scoper.remove_tool_from_scope("sess_b", "write")
        assert scoper.is_tool_allowed("sess_b", "write") is False

    def test_get_scope(self, scoper):
        scoper.set_scope("sess_g", ["a", "b"])
        scope = scoper.get_scope("sess_g")
        assert set(scope) == {"a", "b"}

    def test_clear_scope(self, scoper):
        scoper.set_scope("sess_c", ["chat"])
        scoper.clear_scope("sess_c")
        assert scoper.is_tool_allowed("sess_c", "chat") is True
        assert scoper.get_scope("sess_c") == []

    def test_grant_tool(self, scoper):
        scoper.grant_tool("super_tool", "sess_s")
        assert scoper.is_tool_allowed("sess_s", "super_tool") is True

    def test_revoke_tool(self, scoper):
        scoper.grant_tool("secret", "sess_t")
        scoper.revoke_tool("secret", "sess_t")
        assert scoper.is_tool_allowed("sess_t", "secret") is True


class TestAuditStore:
    @pytest.fixture
    def store(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            path = f.name
        store = AuditStore(json_path=path)
        yield store

    def test_append_and_count(self, store):
        store.append(AuditEntry(session_id="s1", action="test_action"))
        assert store.count() == 1

    def test_get_entries(self, store):
        store.append(AuditEntry(session_id="s1", action="read"))
        store.append(AuditEntry(session_id="s2", action="write"))
        entries = store.get_entries(session_id="s1")
        assert len(entries) == 1
        assert entries[0].action == "read"

    def test_get_entries_filter_by_action(self, store):
        store.append(AuditEntry(session_id="s1", action="read"))
        store.append(AuditEntry(session_id="s1", action="write"))
        entries = store.get_entries(action="read")
        assert len(entries) == 1

    def test_clear(self, store):
        store.append(AuditEntry(session_id="s1", action="x"))
        store.clear()
        assert store.count() == 0

    def test_append_without_file(self):
        store = AuditStore()
        store.append(AuditEntry(session_id="s1", action="test"))
        assert store.count() == 1

    def test_log_action_function(self):
        store = AuditStore()
        entry = log_action("sess_1", "file_read", {"path": "/tmp"}, success=True, store=store)
        assert entry.session_id == "sess_1"
        assert entry.action == "file_read"
        assert store.count() == 1


class TestSecurityManager:
    @pytest.fixture
    def manager(self):
        m = SecurityManager()
        m.token_validator.register_api_key("admin-key", {"role": "admin"})
        return m

    def test_authorize_request_passes(self, manager):
        valid, msg = manager.authorize_request("sess_ok", "admin-key", "chat")
        assert valid is True

    def test_authorize_request_invalid_token(self, manager):
        valid, msg = manager.authorize_request("sess_bad", "wrong-key", "chat")
        assert valid is False
        assert "token" in msg.lower()

    def test_authorize_request_tool_not_allowed(self, manager):
        manager.session_scoper.set_scope("sess_scope", ["chat"])
        valid, msg = manager.authorize_request("sess_scope", "admin-key", "delete")
        assert valid is False
        assert "not allowed" in msg.lower()

    def test_authorize_request_rate_limited(self, manager):
        manager.rate_limiter.max_calls = 2
        for _ in range(2):
            manager.authorize_request("sess_rate", "admin-key", "chat")
        valid, msg = manager.authorize_request("sess_rate", "admin-key", "chat")
        assert valid is False
        assert "rate limit" in msg.lower()

    def test_get_status(self, manager):
        status = manager.get_status("sess_stat")
        assert "session_id" in status
        assert "rate_limit_remaining" in status
        assert "scope" in status
