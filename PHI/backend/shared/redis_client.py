"""Redis Pub/Sub client for inter-service communication.

All services publish and subscribe to channels for async message passing.
"""

import json
import asyncio
import logging
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

import redis.asyncio as aioredis

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    channel: str
    sender: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    message_id: Optional[str] = None


class RedisPubSub:
    """Async Redis Pub/Sub client with automatic reconnection."""

    def __init__(self):
        self._pub: Optional[aioredis.Redis] = None
        self._sub: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._handlers: Dict[str, List[Callable]] = {}
        self._running = False
        self._service_name: str = "unknown"

    async def connect(self, service_name: str = "jarvis") -> None:
        self._service_name = service_name
        self._pub = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        self._sub = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_keepalive=True,
            socket_connect_timeout=5,
        )
        self._pubsub = self._sub.pubsub()
        logger.info(f"RedisPubSub connected for {service_name}")

    async def disconnect(self) -> None:
        self._running = False
        if self._pubsub:
            try: await self._pubsub.unsubscribe()
            except: pass
        if self._pub:
            try: await self._pub.aclose()
            except: pass
        if self._sub:
            try: await self._sub.aclose()
            except: pass

    async def publish(self, channel: str, payload: Dict[str, Any]) -> None:
        msg = Message(
            channel=channel,
            sender=self._service_name,
            payload=payload,
        )
        await self._pub.publish(channel, json.dumps({
            "sender": msg.sender,
            "payload": msg.payload,
            "timestamp": msg.timestamp,
        }))

    def subscribe(self, channel: str, handler: Callable) -> None:
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

    def unsubscribe(self, channel: str, handler: Optional[Callable] = None) -> None:
        if handler and channel in self._handlers:
            self._handlers[channel] = [h for h in self._handlers[channel] if h != handler]
        elif channel in self._handlers:
            del self._handlers[channel]

    async def _listen(self) -> None:
        self._running = True
        channels = list(self._handlers.keys())
        if channels:
            await self._pubsub.subscribe(*channels)
            logger.info(f"Listening on channels: {channels}")
            async for message in self._pubsub.listen():
                if not self._running:
                    break
                if message["type"] != "message":
                    continue
                channel = message["channel"]
                data = json.loads(message["data"])
                msg = Message(
                    channel=channel,
                    sender=data.get("sender", "unknown"),
                    payload=data.get("payload", {}),
                    timestamp=data.get("timestamp", 0),
                )
                for handler in self._handlers.get(channel, []):
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            asyncio.ensure_future(handler(msg))
                        else:
                            handler(msg)
                    except Exception as e:
                        logger.error(f"Handler error on {channel}: {e}")

    async def start_listening(self) -> None:
        asyncio.ensure_future(self._listen())

    async def request(self, channel: str, payload: Dict[str, Any], timeout: float = 10.0) -> Optional[Dict]:
        response_channel = f"response:{self._service_name}:{id(payload)}"
        future: asyncio.Future = asyncio.Future()

        async def response_handler(msg: Message):
            if not future.done():
                future.set_result(msg.payload)

        self.subscribe(response_channel, response_handler)
        payload["_response_channel"] = response_channel
        await self.publish(channel, payload)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout on {channel}")
            return None
        finally:
            self.unsubscribe(response_channel, response_handler)


class RedisClient:
    """Simple synchronous-ish Redis client for non-async contexts."""

    def __init__(self):
        self._client = None

    async def connect(self):
        import redis.asyncio as aioredis
        self._client = await aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> None:
        await self._client.set(key, value, ex=expire)

    async def get(self, key: str) -> Optional[str]:
        return await self._client.get(key)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def publish(self, channel: str, message: str) -> None:
        await self._client.publish(channel, message)
