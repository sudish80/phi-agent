import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from backend.orchestrator.engine.acp.coordinator import ACPSpawnCoordinator, SpawnedAgent


@pytest.fixture
def coordinator():
    return ACPSpawnCoordinator()


@pytest.mark.asyncio
class TestACPSpawnCoordinator:
    async def test_spawn_creates_child_agent(self, coordinator):
        with patch("backend.orchestrator.agent.agent.process", new=AsyncMock(return_value={"reply": "child result"})):
            spawned = await coordinator.spawn("parent_1", "do something")
            assert spawned.parent_session_id == "parent_1"
            assert spawned.status == "running"
            assert spawned.agent_id.startswith("ag_")

    async def test_get_result_returns_child_output(self, coordinator):
        with patch("backend.orchestrator.agent.agent.process", new=AsyncMock(return_value={"reply": "task complete"})):
            spawned = await coordinator.spawn("parent_2", "task")
            result = await coordinator.get_result(spawned.agent_id, timeout=5.0)
            assert result == "task complete"

    async def test_get_result_updates_status(self, coordinator):
        with patch("backend.orchestrator.agent.agent.process", new=AsyncMock(return_value={"reply": "done"})):
            spawned = await coordinator.spawn("parent_3", "work")
            await coordinator.get_result(spawned.agent_id)
            assert spawned.status == "completed"
            assert spawned.result == "done"

    async def test_get_result_timeout(self, coordinator):
        async def slow(instruction, session_id):
            await asyncio.sleep(10)
            return {"reply": "late"}
        with patch("backend.orchestrator.agent.agent.process", new=slow):
            spawned = await coordinator.spawn("parent_4", "slow")
            result = await coordinator.get_result(spawned.agent_id, timeout=0.05)
            assert "Timeout" in result

    async def test_get_result_nonexistent_agent(self, coordinator):
        result = await coordinator.get_result("nonexistent")
        assert result is None

    async def test_cancel_running_agent(self, coordinator):
        async def never_ends(instruction, session_id):
            await asyncio.Future()
        with patch("backend.orchestrator.agent.agent.process", new=never_ends):
            spawned = await coordinator.spawn("parent_5", "long task")
            ok = await coordinator.cancel(spawned.agent_id)
            assert ok is True
            assert spawned.status == "failed"

    async def test_cancel_nonexistent(self, coordinator):
        ok = await coordinator.cancel("ghost")
        assert ok is False

    async def test_list_children(self, coordinator):
        with patch("backend.orchestrator.agent.agent.process", new=AsyncMock(return_value={"reply": ""})):
            await coordinator.spawn("parent_6", "a")
            await coordinator.spawn("parent_6", "b")
            await coordinator.spawn("other_parent", "c")
            children = coordinator.list_children("parent_6")
            assert len(children) == 2

    async def test_cleanup_parent_cancels_children(self, coordinator):
        async def never_ends(instruction, session_id):
            await asyncio.Future()
        with patch("backend.orchestrator.agent.agent.process", new=never_ends):
            await coordinator.spawn("parent_7", "task")
            count = await coordinator.cleanup_parent("parent_7")
            assert count == 1

    async def test_spawned_agent_dataclass(self):
        agent = SpawnedAgent(
            agent_id="ag_123",
            parent_session_id="p1",
            child_session_id="c1",
            task=asyncio.create_task(asyncio.sleep(0)),
            status="running",
        )
        assert agent.agent_id == "ag_123"
        assert agent.status == "running"
