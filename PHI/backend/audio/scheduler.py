import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class AudioScheduler:
    """Background scheduler for audio lifecycle management:
    - Compress old files after 1 hour
    - Cleanup expired temporary files
    - Remove archives older than 7 days
    """

    def __init__(self, audio_manager):
        self._audio_manager = audio_manager
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._compress_job,
            IntervalTrigger(hours=1),
            id="compress_old_audio",
            name="Compress audio files older than 1 hour",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._cleanup_expired_job,
            IntervalTrigger(hours=6),
            id="cleanup_expired_audio",
            name="Delete expired temporary audio files",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._cleanup_archives_job,
            IntervalTrigger(days=1),
            id="cleanup_old_archives",
            name="Delete ZIP archives older than 7 days",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info("Audio scheduler started (compress hourly, cleanup expiry 6h, archive retention 7d)")

    async def _compress_job(self):
        try:
            count = await self._audio_manager.compress_old_files(older_than_hours=1.0)
            if count:
                logger.info(f"Scheduler: compressed {count} files")
        except Exception as e:
            logger.warning(f"Scheduler compress job failed: {e}")

    async def _cleanup_expired_job(self):
        try:
            count = await self._audio_manager.cleanup_expired()
            if count:
                logger.info(f"Scheduler: cleaned up {count} expired files")
        except Exception as e:
            logger.warning(f"Scheduler cleanup expired job failed: {e}")

    async def _cleanup_archives_job(self):
        try:
            await self._audio_manager.cleanup_old_archives(retention_days=7)
        except Exception as e:
            logger.warning(f"Scheduler cleanup archives job failed: {e}")

    def stop(self):
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Audio scheduler stopped")
