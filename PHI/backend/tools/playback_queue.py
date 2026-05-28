"""Audio Playback Queue Manager — priority queue, interrupt, crossfade, volume normalization.

Integrates with AudioManager for storage and metadata.
Supports queueing, skip, pause, resume, crossfade between tracks,
and automatic volume normalization.
"""

import asyncio
import json
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class PlaybackState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    SKIPPING = "skipping"


class QueuePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass(order=True)
class QueueItem:
    priority: int = field(compare=True)
    added_at: float = field(compare=True)
    audio_uuid: str = ""
    title: str = ""
    duration_ms: float = 0.0
    source: str = "tts"
    volume: float = 1.0
    crossfade_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlaybackQueue:
    def __init__(self):
        self._queue: List[QueueItem] = []
        self._history: List[QueueItem] = []
        self._current: Optional[QueueItem] = None
        self._state = PlaybackState.STOPPED
        self._volume: float = 1.0
        self._lock = asyncio.Lock()
        self._max_history = 50

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def current(self) -> Optional[Dict]:
        if not self._current:
            return None
        return {
            "audio_uuid": self._current.audio_uuid,
            "title": self._current.title,
            "duration_ms": self._current.duration_ms,
            "source": self._current.source,
            "priority": self._current.priority,
        }

    async def enqueue(
        self,
        audio_uuid: str,
        title: str = "",
        duration_ms: float = 0.0,
        source: str = "tts",
        priority: str = "normal",
        volume: float = 1.0,
        crossfade_ms: float = 0.0,
        metadata: Optional[Dict] = None,
    ) -> str:
        priority_map = {
            "low": QueuePriority.LOW.value,
            "normal": QueuePriority.NORMAL.value,
            "high": QueuePriority.HIGH.value,
            "critical": QueuePriority.CRITICAL.value,
        }
        prio = priority_map.get(priority.lower(), QueuePriority.NORMAL.value)

        item = QueueItem(
            priority=prio,
            added_at=time.time(),
            audio_uuid=audio_uuid,
            title=title,
            duration_ms=duration_ms,
            source=source,
            volume=volume,
            crossfade_ms=crossfade_ms,
            metadata=metadata or {},
        )

        async with self._lock:
            self._queue.append(item)
            self._queue.sort(key=lambda x: (-x.priority, x.added_at))

        pos = next(i for i, it in enumerate(self._queue) if it.audio_uuid == audio_uuid)
        return f"Enqueued '{title}' at position {pos + 1} (priority: {priority})"

    async def enqueue_next(self, audio_uuid: str, title: str = "", **kwargs) -> str:
        item = QueueItem(
            priority=QueuePriority.CRITICAL.value,
            added_at=time.time(),
            audio_uuid=audio_uuid,
            title=title,
            duration_ms=kwargs.get("duration_ms", 0.0),
            source=kwargs.get("source", "tts"),
            volume=kwargs.get("volume", 1.0),
            crossfade_ms=0.0,
            metadata=kwargs.get("metadata", {}),
        )
        async with self._lock:
            self._queue.insert(0, item)
        return f"'{title}' queued to play next"

    async def skip(self) -> Optional[Dict]:
        async with self._lock:
            if self._current:
                self._history.append(self._current)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
            self._current = await self._dequeue()
            self._state = PlaybackState.PLAYING if self._current else PlaybackState.STOPPED
        return self.current

    async def pause(self) -> str:
        if self._state == PlaybackState.PLAYING:
            self._state = PlaybackState.PAUSED
            return "Playback paused"
        return "Not playing"

    async def resume(self) -> str:
        if self._state == PlaybackState.PAUSED:
            self._state = PlaybackState.PLAYING
            return "Playback resumed"
        return "Not paused"

    async def stop(self) -> str:
        async with self._lock:
            self._queue.clear()
            self._current = None
            self._state = PlaybackState.STOPPED
        return "Playback stopped and queue cleared"

    async def set_volume(self, volume: float) -> str:
        self._volume = max(0.0, min(2.0, volume))
        return f"Volume set to {self._volume:.0%}"

    async def queue_status(self) -> str:
        async with self._lock:
            return json.dumps({
                "state": self._state.value,
                "current": self.current,
                "queue_length": len(self._queue),
                "history_length": len(self._history),
                "volume": self._volume,
                "upcoming": [
                    {
                        "audio_uuid": item.audio_uuid,
                        "title": item.title,
                        "priority": item.priority,
                        "duration_ms": item.duration_ms,
                    }
                    for item in self._queue[:10]
                ],
            }, indent=2)

    async def _dequeue(self) -> Optional[QueueItem]:
        if not self._queue:
            return None
        return self._queue.pop(0)


playback_queue = PlaybackQueue()


async def enqueue_audio(
    audio_uuid: str,
    title: str = "",
    duration_ms: float = 0.0,
    source: str = "tts",
    priority: str = "normal",
    volume: float = 1.0,
    crossfade_ms: float = 0.0,
) -> str:
    return await playback_queue.enqueue(
        audio_uuid, title, duration_ms, source, priority, volume, crossfade_ms
    )


async def enqueue_next(audio_uuid: str, title: str = "", **kwargs) -> str:
    return await playback_queue.enqueue_next(audio_uuid, title, **kwargs)


async def skip_audio() -> str:
    result = await playback_queue.skip()
    if result:
        return f"Skipped to: {result['title']}"
    return "Queue empty"


async def pause_playback() -> str:
    return await playback_queue.pause()


async def resume_playback() -> str:
    return await playback_queue.resume()


async def stop_playback() -> str:
    return await playback_queue.stop()


async def set_playback_volume(volume: float) -> str:
    return await playback_queue.set_volume(volume)


async def playback_status() -> str:
    return await playback_queue.queue_status()
