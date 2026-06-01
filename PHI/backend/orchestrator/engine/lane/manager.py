"""Command Lane — concurrency lanes for session work.

Mirrors openclaw's lanes.ts with priorities:
  foreground > normal > background
"""

import asyncio
import logging
import time
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class LanePriority(IntEnum):
    BACKGROUND = 0
    NORMAL = 1
    FOREGROUND = 2


@dataclass(order=True)
class LaneTask:
    priority: LanePriority
    enqueued_at: float = field(compare=False)
    task_id: str = field(compare=False)
    coro: Callable[[], Awaitable[Any]] = field(compare=False)
    session_id: str = field(compare=False, default="")
    owner: str = field(compare=False, default="")


class CommandLane:
    """A single concurrency lane that processes tasks in priority order."""

    def __init__(self, name: str, max_concurrent: int = 1):
        self.name = name
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: int = 0
        self._max_concurrent = max_concurrent
        self._worker_task: Optional[asyncio.Task] = None
        self._shutdown = False

    async def enqueue(self, task: LaneTask) -> None:
        await self._queue.put(task)
        logger.debug("Lane %s: enqueued task %s (priority %s)", self.name, task.task_id, task.priority.name)

    async def _worker(self) -> None:
        while not self._shutdown:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            self._running += 1
            try:
                result = await task.coro()
                logger.debug("Lane %s: task %s completed", self.name, task.task_id)
            except Exception as e:
                logger.exception("Lane %s: task %s failed: %s", self.name, task.task_id, e)
            finally:
                self._running -= 1
                self._queue.task_done()

    def start(self) -> None:
        if self._worker_task is None:
            self._shutdown = False
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Lane %s: started", self.name)

    async def stop(self) -> None:
        self._shutdown = True
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("Lane %s: stopped", self.name)

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def running(self) -> int:
        return self._running


class LaneManager:
    """Manages session-specific lanes + global lanes."""

    def __init__(self):
        self._global = CommandLane("global", max_concurrent=5)
        self._session_lanes: Dict[str, CommandLane] = {}
        self._cron_lane = CommandLane("cron", max_concurrent=3)
        self._lock = asyncio.Lock()

    def start(self) -> None:
        self._global.start()
        self._cron_lane.start()

    async def stop(self) -> None:
        await self._global.stop()
        await self._cron_lane.stop()
        async with self._lock:
            for lane in self._session_lanes.values():
                await lane.stop()
            self._session_lanes.clear()

    async def get_session_lane(self, session_id: str) -> CommandLane:
        async with self._lock:
            if session_id not in self._session_lanes:
                lane = CommandLane(f"session:{session_id}", max_concurrent=1)
                lane.start()
                self._session_lanes[session_id] = lane
            return self._session_lanes[session_id]

    async def enqueue_foreground(self, session_id: str, task_id: str,
                                  coro: Callable[[], Awaitable[Any]],
                                  owner: str = "") -> None:
        lane = await self.get_session_lane(session_id)
        await lane.enqueue(LaneTask(
            priority=LanePriority.FOREGROUND,
            enqueued_at=time.time(),
            task_id=task_id,
            coro=coro,
            session_id=session_id,
            owner=owner,
        ))

    async def enqueue_background(self, session_id: str, task_id: str,
                                   coro: Callable[[], Awaitable[Any]],
                                   owner: str = "") -> None:
        lane = await self.get_session_lane(session_id)
        await lane.enqueue(LaneTask(
            priority=LanePriority.BACKGROUND,
            enqueued_at=time.time(),
            task_id=task_id,
            coro=coro,
            session_id=session_id,
            owner=owner,
        ))

    async def enqueue_cron(self, task_id: str,
                            coro: Callable[[], Awaitable[Any]]) -> None:
        await self._cron_lane.enqueue(LaneTask(
            priority=LanePriority.BACKGROUND,
            enqueued_at=time.time(),
            task_id=task_id,
            coro=coro,
        ))


# Global singleton
lane_manager = LaneManager()
