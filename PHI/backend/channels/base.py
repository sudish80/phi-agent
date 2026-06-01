"""Channel Plugin Interface — unified contract for all messaging backends."""

from typing import Any, Callable, Dict, List, Optional, Awaitable
from dataclasses import dataclass, field
from enum import Enum


class ChannelEvent(Enum):
    MESSAGE = "message"
    EDIT = "edit"
    DELETE = "delete"
    REACTION = "reaction"
    TYPING = "typing"
    MEMBER_JOIN = "member_join"
    MEMBER_LEAVE = "member_leave"


@dataclass
class ChannelMessage:
    id: str
    channel_id: str
    author_id: str
    author_name: str = ""
    content: str = ""
    attachments: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    thread_id: Optional[str] = None
    is_dm: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelConfig:
    enabled: bool = True
    dm_policy: str = "open"  # open | pairing | closed
    allow_from: List[str] = field(default_factory=lambda: ["*"])
    deny_from: List[str] = field(default_factory=list)
    command_prefix: str = "/"
    respond_to_mentions: bool = True
    respond_to_dms: bool = True


class BaseChannel:
    """Base class for all channel plugins."""

    name: str = ""
    config: ChannelConfig = field(default_factory=ChannelConfig)

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    async def send_message(self, channel_id: str, content: str,
                            reply_to: Optional[str] = None) -> str:
        raise NotImplementedError

    async def send_typing(self, channel_id: str) -> None:
        pass

    async def on_event(self, event: ChannelEvent, data: ChannelMessage) -> None:
        pass


class ChannelRegistry:
    """Registry of all installed channel plugins."""

    def __init__(self):
        self._channels: Dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        self._channels[channel.name] = channel

    def get(self, name: str) -> Optional[BaseChannel]:
        return self._channels.get(name)

    def list_channels(self) -> List[BaseChannel]:
        return list(self._channels.values())

    async def start_all(self) -> None:
        for ch in self._channels.values():
            if ch.config.enabled:
                await ch.start()

    async def stop_all(self) -> None:
        for ch in self._channels.values():
            await ch.stop()


channel_registry = ChannelRegistry()
