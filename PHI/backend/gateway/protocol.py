"""Gateway Protocol — RPC definitions for agent↔client communication."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


class GatewayOp(Enum):
    HELLO = "hello"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    MESSAGE_CREATE = "message_create"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_DELETE = "message_delete"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    RECONNECT = "reconnect"
    INVALID_SESSION = "invalid_session"


@dataclass
class GatewayPayload:
    op: GatewayOp
    data: Dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    session_id: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "op": self.op.value,
            "d": self.data,
            "seq": self.seq,
            "session_id": self.session_id,
        })

    @classmethod
    def from_json(cls, raw: str) -> "GatewayPayload":
        obj = json.loads(raw)
        return cls(
            op=GatewayOp(obj["op"]),
            data=obj.get("d", {}),
            seq=obj.get("seq", 0),
            session_id=obj.get("session_id", ""),
        )


@dataclass
class MessageCreateData:
    content: str
    channel_id: str = ""
    author_id: str = ""
    attachments: List[str] = field(default_factory=list)
    session_id: str = ""


@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    max_payload_size: int = 4096 * 100
    heartbeat_interval: float = 30.0
    reconnect_delay: float = 5.0
