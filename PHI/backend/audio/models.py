import uuid
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime


class AudioCategory:
    GENERATED_TTS = "generated/tts"
    GENERATED_RESPONSES = "generated/responses"
    GENERATED_NOTIFICATIONS = "generated/notifications"
    GENERATED_MUSIC = "generated/music"
    GENERATED_TEMPORARY = "generated/temporary"
    RECORDINGS_CONVERSATIONS = "recordings/conversations"
    RECORDINGS_COMMANDS = "recordings/commands"
    RECORDINGS_MEETINGS = "recordings/meetings"
    PROCESSED_CLEANED = "processed/cleaned"
    PROCESSED_NORMALIZED = "processed/normalized"
    PROCESSED_COMPRESSED = "processed/compressed"
    PROCESSED_EMBEDDINGS = "processed/embeddings"
    CACHE_REPEATED_PHRASES = "cache/repeated_phrases"
    CACHE_INSTANT_RESPONSES = "cache/instant_responses"

    @classmethod
    def all(cls) -> List[str]:
        return [v for k, v in cls.__dict__.items() if not k.startswith("_") and isinstance(v, str)]


@dataclass
class AudioEntry:
    uuid: str = field(default_factory=lambda: uuid.uuid4().hex)
    filename: str = ""
    original_filename: str = ""
    file_size: int = 0
    format: str = "mp3"
    duration_ms: float = 0.0
    category: str = AudioCategory.GENERATED_TTS
    subcategory: str = ""
    sha256_hash: str = ""
    audio_url: str = ""
    transcript: str = ""
    speaker: str = ""
    emotion: str = "neutral"
    sample_rate: int = 24000
    channels: int = 1
    metadata_json: str = "{}"
    linked_conversation_id: str = ""
    linked_screenshot_id: str = ""
    linked_task_id: str = ""
    linked_thought_id: str = ""
    source: str = "elevenlabs"
    is_compressed: bool = False
    archive_path: str = ""
    created_at: str = ""
    accessed_at: str = ""
    expires_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_compressed"] = int(d["is_compressed"])
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AudioEntry":
        d["is_compressed"] = bool(d.get("is_compressed", False))
        return cls(**d)


@dataclass
class AudioSearchResult:
    uuid: str
    filename: str
    category: str
    transcript: str
    speaker: str
    emotion: str
    duration_ms: float
    file_size: int
    audio_url: str
    linked_conversation_id: str
    created_at: str
    score: float = 0.0
