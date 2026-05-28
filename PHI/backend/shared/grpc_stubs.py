"""gRPC stubs for inter-service communication.

Defines protobuf-like message structures and async clients
for service-to-service RPC calls.
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

from .redis_client import RedisPubSub

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    NOT_FOUND = "not_found"


@dataclass
class RPCRequest:
    method: str
    params: Dict[str, Any]
    request_id: str
    timeout: float = 30.0


@dataclass
class RPCResponse:
    status: ServiceStatus
    data: Dict[str, Any]
    error: Optional[str] = None
    request_id: Optional[str] = None


class ServiceStub:
    """Base class for service stubs that communicate via Redis."""

    def __init__(self, service_name: str, pubsub: RedisPubSub):
        self.service_name = service_name
        self.pubsub = pubsub
        self._request_id = 0

    def _next_id(self) -> str:
        self._request_id += 1
        return f"{self.service_name}:{self._request_id}"

    async def call(self, method: str, params: Dict[str, Any] = None,
                   timeout: float = 30.0) -> RPCResponse:
        request_id = self._next_id()
        request = RPCRequest(
            method=method,
            params=params or {},
            request_id=request_id,
            timeout=timeout,
        )
        channel = f"rpc:{self.service_name}"
        response = await self.pubsub.request(channel, asdict(request), timeout=timeout)
        if response is None:
            return RPCResponse(
                status=ServiceStatus.ERROR,
                data={},
                error=f"No response from {self.service_name}",
                request_id=request_id,
            )
        return RPCResponse(
            status=ServiceStatus(response.get("status", "error")),
            data=response.get("data", {}),
            error=response.get("error"),
            request_id=response.get("request_id"),
        )


class VisionStub(ServiceStub):
    """Stub for Vision Service."""

    def __init__(self, pubsub: RedisPubSub):
        super().__init__("vision", pubsub)

    async def analyze_image(self, image_base64: str, query: str = "") -> Dict:
        resp = await self.call("analyze", {"image": image_base64, "query": query})
        return resp.data

    async def detect_objects(self, image_base64: str = None) -> List[Dict]:
        resp = await self.call("detect_objects", {"image": image_base64 or ""})
        return resp.data.get("objects", [])

    async def recognize_face(self, image_base64: str = None) -> List[Dict]:
        resp = await self.call("recognize_face", {"image": image_base64 or ""})
        return resp.data.get("faces", [])

    async def detect_colors(self, image_base64: str = None) -> List[Dict]:
        resp = await self.call("detect_colors", {"image": image_base64 or ""})
        return resp.data.get("colors", [])

    async def get_status(self) -> Dict:
        resp = await self.call("status")
        return resp.data


class HearingStub(ServiceStub):
    """Stub for Hearing Service."""

    def __init__(self, pubsub: RedisPubSub):
        super().__init__("hearing", pubsub)

    async def transcribe(self, audio_base64: str) -> Dict:
        resp = await self.call("transcribe", {"audio": audio_base64})
        return resp.data

    async def is_speaking(self) -> bool:
        resp = await self.call("is_speaking")
        return resp.data.get("speaking", False)

    async def get_conversation_buffer(self) -> List[str]:
        resp = await self.call("get_buffer")
        return resp.data.get("buffer", [])


class SpeechStub(ServiceStub):
    """Stub for Speech Service."""

    def __init__(self, pubsub: RedisPubSub):
        super().__init__("speech", pubsub)

    async def synthesize(self, text: str, emotion: str = "neutral",
                         return_visemes: bool = True) -> Dict:
        resp = await self.call("synthesize", {
            "text": text,
            "emotion": emotion,
            "return_visemes": return_visemes,
        })
        return resp.data

    async def get_voice_list(self) -> List[Dict]:
        resp = await self.call("get_voices")
        return resp.data.get("voices", [])


class ActionStub(ServiceStub):
    """Stub for Action Service."""

    def __init__(self, pubsub: RedisPubSub):
        super().__init__("action", pubsub)

    async def send_email(self, to: str, subject: str, body: str) -> Dict:
        resp = await self.call("send_email", {
            "to": to, "subject": subject, "body": body,
        })
        return resp.data

    async def create_calendar_event(self, summary: str, start: str, end: str,
                                    description: str = "") -> Dict:
        resp = await self.call("create_event", {
            "summary": summary, "start": start, "end": end, "description": description,
        })
        return resp.data

    async def search_web(self, query: str) -> Dict:
        resp = await self.call("web_search", {"query": query})
        return resp.data

    async def control_light(self, room: str, state: str) -> Dict:
        resp = await self.call("control_light", {"room": room, "state": state})
        return resp.data

    async def set_temperature(self, degrees: float) -> Dict:
        resp = await self.call("set_temperature", {"degrees": degrees})
        return resp.data

    async def open_application(self, app_name: str) -> Dict:
        resp = await self.call("open_app", {"app_name": app_name})
        return resp.data

    async def get_weather(self, location: str = "") -> Dict:
        resp = await self.call("get_weather", {"location": location})
        return resp.data

    async def set_reminder(self, text: str, time: str) -> Dict:
        resp = await self.call("set_reminder", {"text": text, "time": time})
        return resp.data


class MemoryStub(ServiceStub):
    """Stub for Memory Service."""

    def __init__(self, pubsub: RedisPubSub):
        super().__init__("memory", pubsub)

    async def store_episodic(self, content: str, metadata: Dict = None) -> Dict:
        resp = await self.call("store_episodic", {
            "content": content, "metadata": metadata or {},
        })
        return resp.data

    async def store_semantic(self, fact: str, metadata: Dict = None) -> Dict:
        resp = await self.call("store_semantic", {
            "fact": fact, "metadata": metadata or {},
        })
        return resp.data

    async def query_memory(self, query: str, n_results: int = 5,
                           memory_type: str = "all") -> List[Dict]:
        resp = await self.call("query", {
            "query": query, "n_results": n_results, "type": memory_type,
        })
        return resp.data.get("results", [])

    async def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        resp = await self.call("recent_conversations", {"limit": limit})
        return resp.data.get("conversations", [])

    async def get_memory_palace_map(self) -> Dict:
        resp = await self.call("palace_map")
        return resp.data

    async def consolidate_memories(self) -> Dict:
        resp = await self.call("consolidate")
        return resp.data
