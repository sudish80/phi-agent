"""WebChat channel — browser-based chat UI over HTTP/WS."""

import logging
from typing import Optional
from backend.channels.base import BaseChannel, ChannelConfig, ChannelMessage, ChannelEvent

logger = logging.getLogger(__name__)


class WebChatChannel(BaseChannel):
    """Built-in browser chat surface served via the HTTP API."""

    name = "webchat"

    def __init__(self):
        self.config = ChannelConfig(
            enabled=True,
            dm_policy="open",
            respond_to_dms=True,
        )
        self._messages: list = []

    async def start(self) -> None:
        logger.info("WebChat channel ready at /chat endpoint")

    async def stop(self) -> None:
        logger.info("WebChat channel stopped")

    async def send_message(self, channel_id: str, content: str,
                            reply_to: Optional[str] = None) -> str:
        self._messages.append({"role": "assistant", "content": content})
        return content

    def get_history(self, limit: int = 50) -> list:
        return self._messages[-limit:]


webchat = WebChatChannel()
