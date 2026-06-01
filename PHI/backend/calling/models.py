import uuid
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


class CallState(str, Enum):
    idle = "idle"
    ringing = "ringing"
    connecting = "connecting"
    connected = "connected"
    ended = "ended"
    missed = "missed"
    declined = "declined"


class MediaType(str, Enum):
    audio = "audio"
    video = "video"


@dataclass
class CallSession:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    caller_id: str = ""
    callee_id: str = ""
    state: CallState = CallState.idle
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_sec: float = 0.0
    media_type: MediaType = MediaType.audio
    sdp_offer: str = ""
    sdp_answer: str = ""
    ice_candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        d["media_type"] = self.media_type.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CallSession":
        if "state" in d:
            d["state"] = CallState(d["state"])
        if "media_type" in d:
            d["media_type"] = MediaType(d["media_type"])
        return cls(**d)


@dataclass
class VADConfig:
    mode: int = 1
    frame_ms: int = 30
    padding_ms: int = 300
    threshold: float = 0.5

    def __post_init__(self):
        self.mode = max(0, min(3, self.mode))
        self.frame_ms = max(10, min(60, self.frame_ms))
        self.padding_ms = max(100, min(500, self.padding_ms))
        self.threshold = max(0.0, min(1.0, self.threshold))


@dataclass
class CallLog:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    session_id: str = ""
    event: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CallLog":
        return cls(**d)
