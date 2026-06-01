"""Gateway Server — WebSocket-based RPC for agent communication."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Set
from dataclasses import dataclass, field

from backend.gateway.protocol import (
    GatewayOp, GatewayPayload, GatewayConfig, MessageCreateData,
)

logger = logging.getLogger(__name__)


@dataclass
class GatewayClient:
    session_id: str
    connected_at: float
    last_heartbeat: float
    seq: int = 0


class GatewayServer:
    """WebSocket gateway for external clients to communicate with the agent."""

    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        self._clients: Dict[str, GatewayClient] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False
        self._message_handler = None

    def on_message(self, handler):
        self._message_handler = handler

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("Gateway starting on %s:%d", self.config.host, self.config.port)
        # In production, start WebSocket server here
        # For now, the gateway is a protocol layer over the existing HTTP API
        logger.info("Gateway ready (protocol layer)")

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Gateway stopped")

    async def send_message(self, session_id: str, payload: GatewayPayload) -> None:
        client = self._clients.get(session_id)
        if not client:
            logger.debug("No client for session %s", session_id)
            return
        client.seq += 1
        payload.seq = client.seq
        # In production, send via WebSocket
        logger.debug("Gateway -> %s: %s", session_id, payload.op.value)

    async def broadcast(self, payload: GatewayPayload) -> None:
        for sid in list(self._clients.keys()):
            await self.send_message(sid, payload)


# Global singleton
gateway_server = GatewayServer()
