"""ACP — Agent Communication Protocol for spawning child agent sessions.

Mirrors openclaw's acp-spawn.ts.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
from dataclasses import dataclass, field

from backend.orchestrator.engine.policy.resolver import ToolPolicy

logger = logging.getLogger(__name__)


@dataclass
class SpawnedAgent:
    agent_id: str
    parent_session_id: str
    child_session_id: str
    task: asyncio.Task
    created_at: float = 0.0
    status: str = "running"  # running | completed | failed
    result: Optional[str] = None
    tool_policy: Optional[ToolPolicy] = None


class ACPSpawnCoordinator:
    """Coordinates spawning child agent sessions from a parent agent."""

    def __init__(self):
        self._children: Dict[str, SpawnedAgent] = {}
        self._lock = asyncio.Lock()

    async def spawn(self, parent_session_id: str, instruction: str,
                     tool_policy: Optional[ToolPolicy] = None,
                     sandboxed: bool = False) -> SpawnedAgent:
        """Spawn a child agent with its own session."""
        from backend.orchestrator.agent import agent

        child_session_id = f"{parent_session_id}_child_{uuid.uuid4().hex[:8]}"
        agent_id = f"ag_{uuid.uuid4().hex[:12]}"

        async def _run_child():
            try:
                result = await agent.process(instruction, child_session_id)
                return result.get("reply", "")
            except Exception as e:
                logger.exception("Child agent %s failed: %s", agent_id, e)
                return f"Error: {e}"

        task = asyncio.create_task(_run_child())

        spawned = SpawnedAgent(
            agent_id=agent_id,
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
            task=task,
            created_at=time.time(),
            tool_policy=tool_policy,
        )

        async with self._lock:
            self._children[agent_id] = spawned

        logger.info("ACP: spawned child %s for parent %s", agent_id, parent_session_id)
        return spawned

    async def get_result(self, agent_id: str, timeout: float = 60.0) -> Optional[str]:
        """Wait for a child agent to complete and return its result."""
        async with self._lock:
            spawned = self._children.get(agent_id)
        if not spawned:
            return None

        try:
            result = await asyncio.wait_for(spawned.task, timeout=timeout)
            async with self._lock:
                spawned.status = "completed"
                spawned.result = result
            return result
        except asyncio.TimeoutError:
            async with self._lock:
                spawned.status = "failed"
                spawned.result = "Timeout"
            return "Timeout waiting for child agent"

    async def cancel(self, agent_id: str) -> bool:
        async with self._lock:
            spawned = self._children.get(agent_id)
        if not spawned:
            return False
        spawned.task.cancel()
        spawned.status = "failed"
        return True

    def list_children(self, parent_session_id: str) -> List[SpawnedAgent]:
        return [s for s in self._children.values()
                if s.parent_session_id == parent_session_id]

    async def cleanup_parent(self, parent_session_id: str) -> int:
        """Cancel all children of a parent session."""
        count = 0
        for spawned in self.list_children(parent_session_id):
            if spawned.status == "running":
                spawned.task.cancel()
                count += 1
        return count


# Global singleton
acp_coordinator = ACPSpawnCoordinator()
