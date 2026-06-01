"""Cron — scheduled agent tasks.

Mirrors openclaw's cron scheduling with agent-tools.cron-scope.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CronJob:
    name: str
    schedule: str  # cron expression or interval like "5m", "1h"
    task: Callable[[], Awaitable[None]]
    enabled: bool = True
    last_run: float = 0.0
    interval_seconds: float = 0.0
    session_id: str = ""


class CronScheduler:
    """Simple scheduler for periodic agent tasks."""

    def __init__(self):
        self._jobs: Dict[str, CronJob] = {}
        self._worker: Optional[asyncio.Task] = None
        self._shutdown = False

    def register(self, name: str, schedule: str,
                  task: Callable[[], Awaitable[None]],
                  session_id: str = "") -> None:
        interval = self._parse_schedule(schedule)
        self._jobs[name] = CronJob(
            name=name, schedule=schedule, task=task,
            interval_seconds=interval, session_id=session_id,
        )
        logger.info("Cron: registered '%s' (%s, every %.0fs)", name, schedule, interval)

    def _parse_schedule(self, schedule: str) -> float:
        """Parse simple interval strings like '5m', '1h', '30s'."""
        schedule = schedule.strip().lower()
        if schedule.endswith('s'):
            return float(schedule[:-1])
        if schedule.endswith('m'):
            return float(schedule[:-1]) * 60
        if schedule.endswith('h'):
            return float(schedule[:-1]) * 3600
        if schedule.endswith('d'):
            return float(schedule[:-1]) * 86400
        return float(schedule)

    def unregister(self, name: str) -> None:
        self._jobs.pop(name, None)
        logger.info("Cron: unregistered '%s'", name)

    async def _run_loop(self) -> None:
        while not self._shutdown:
            now = time.time()
            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if now - job.last_run >= job.interval_seconds:
                    job.last_run = now
                    try:
                        await job.task()
                    except Exception as e:
                        logger.exception("Cron job '%s' failed: %s", job.name, e)
            await asyncio.sleep(5)

    def start(self) -> None:
        if self._worker is None:
            self._shutdown = False
            self._worker = asyncio.create_task(self._run_loop())
            logger.info("Cron scheduler started with %d jobs", len(self._jobs))

    async def stop(self) -> None:
        self._shutdown = True
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None
        logger.info("Cron scheduler stopped")

    @property
    def job_count(self) -> int:
        return len(self._jobs)


# Global singleton
cron_scheduler = CronScheduler()
