"""CronScheduler — periodic background task runner for scheduled actions."""

import asyncio
import logging
from typing import Optional

from backend.automation.schedule import get_schedule_manager

logger = logging.getLogger(__name__)


class CronScheduler:
    """Background scheduler that periodically checks for due schedule entries and executes them."""

    def __init__(self, interval: float = 30.0):
        self._interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def _execute_action(self, entry) -> None:
        from backend.automation.tasks import task_queue
        try:
            task = task_queue.create_task(
                name=entry.action,
                workflow=entry.action,
                params=entry.params,
            )
            await task_queue.execute_task(task.id)
            logger.info("Cron: executed scheduled action '%s' (task=%s)", entry.action, task.id)
        except Exception as e:
            logger.warning("Cron: action '%s' failed: %s", entry.action, e)

    async def _loop(self):
        while True:
            try:
                manager = get_schedule_manager()
                due = manager.check_due()
                for entry in due:
                    await self._execute_action(entry)
            except Exception as e:
                logger.warning("Cron scheduler cycle failed: %s", e)
            await asyncio.sleep(self._interval)

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("CronScheduler started (interval=%ss)", self._interval)

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("CronScheduler stopped")


cron_scheduler = CronScheduler()
