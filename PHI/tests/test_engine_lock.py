import asyncio
import pytest
from backend.orchestrator.engine.lock import SessionWriteLock


@pytest.fixture
def lock():
    return SessionWriteLock()


@pytest.mark.asyncio
class TestSessionWriteLock:
    async def test_acquire_and_release(self, lock):
        ok = await lock.acquire("session_1", "owner_a")
        assert ok is True
        assert await lock.is_locked("session_1") is True

        await lock.release("session_1", "owner_a")
        assert await lock.is_locked("session_1") is False

    async def test_two_sessions_dont_block(self, lock):
        ok1 = await lock.acquire("sess_a", "owner_a")
        ok2 = await lock.acquire("sess_b", "owner_b")
        assert ok1 is True
        assert ok2 is True

    async def test_second_owner_blocked(self, lock):
        await lock.acquire("sess_x", "owner_a")
        ok = await lock.acquire("sess_x", "owner_b")
        assert ok is False

    async def test_same_owner_reentrant(self, lock):
        await lock.acquire("sess_r", "owner_a")
        ok = await lock.acquire("sess_r", "owner_a")
        assert ok is True

    async def test_ttl_expiry_allows_steal(self, lock):
        await lock.acquire("sess_ttl", "owner_a", ttl=0.1)
        await asyncio.sleep(0.15)
        ok = await lock.acquire("sess_ttl", "owner_b")
        assert ok is True

    async def test_is_locked_after_ttl_expiry(self, lock):
        await lock.acquire("sess_exp", "owner_a", ttl=0.1)
        await asyncio.sleep(0.15)
        locked = await lock.is_locked("sess_exp")
        assert locked is False

    async def test_get_owner(self, lock):
        await lock.acquire("sess_own", "owner_a")
        owner = await lock.get_owner("sess_own")
        assert owner == "owner_a"

    async def test_get_owner_none_when_not_locked(self, lock):
        owner = await lock.get_owner("no_lock")
        assert owner is None

    async def test_get_owner_after_expiry(self, lock):
        await lock.acquire("sess_exp2", "owner_a", ttl=0.1)
        await asyncio.sleep(0.15)
        owner = await lock.get_owner("sess_exp2")
        assert owner is None

    async def test_wrong_owner_release_fails(self, lock):
        await lock.acquire("sess_wr", "owner_a")
        await lock.release("sess_wr", "owner_b")
        assert await lock.is_locked("sess_wr") is True

    async def test_cleanup_expired(self, lock):
        lock._locks["expired"] = type("E", (), {"acquired_at": 0, "ttl": 0.01})()
        lock._locks["active"] = type("E", (), {"acquired_at": 9999999999, "ttl": 30})()
        count = lock.cleanup_expired()
        assert count == 1
        assert "active" in lock._locks
        assert "expired" not in lock._locks
