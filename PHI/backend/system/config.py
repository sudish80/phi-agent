"""Centralized system configuration loaded from environment variables.

Provides a SystemConfig dataclass with all configuration from env vars,
singleton instance, serialization to/from dict, and .env file write support.
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


@dataclass
class SystemConfig:
    log_level: str = "INFO"
    tool_profile: str = "full"
    debug_mode: bool = False

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False
    redis_pubsub_channels: List[str] = field(default_factory=lambda: [
        "phi:commands", "phi:events", "phi:system",
    ])

    session_db_path: str = ""
    thread_db_path: str = ""
    canvas_db_path: str = ""

    audio_store_path: str = ""
    audio_max_storage_gb: float = 10.0

    backup_dir: str = ""
    backup_auto_interval_hours: int = 6
    backup_keep_count: int = 10

    jwt_secret: str = "change-me"
    rate_limit_max: int = 100
    rate_limit_window: int = 60

    calling_default_provider: str = "webrtc"
    calling_recording_enabled: bool = False

    health_check_interval: int = 60
    metrics_enabled: bool = True

    def __post_init__(self):
        base = str(ROOT_DIR)
        if not self.session_db_path:
            self.session_db_path = os.path.join(base, "data", "sessions.db")
        if not self.thread_db_path:
            self.thread_db_path = os.path.join(base, "data", "threads.db")
        if not self.canvas_db_path:
            self.canvas_db_path = os.path.join(base, "data", "canvases.db")
        if not self.audio_store_path:
            self.audio_store_path = os.path.join(base, "workspace", "audio")
        if not self.backup_dir:
            self.backup_dir = os.path.join(base, "backups")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemConfig":
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@lru_cache()
def load_from_env() -> SystemConfig:
    vals: Dict[str, Any] = {}

    vals["log_level"] = os.getenv("LOG_LEVEL", "INFO")
    vals["tool_profile"] = os.getenv("TOOL_PROFILE", "full")
    vals["debug_mode"] = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")

    vals["openai_api_key"] = os.getenv("OPENAI_API_KEY") or None
    vals["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY") or None
    vals["nvidia_api_key"] = os.getenv("NVIDIA_API_KEY") or None
    vals["google_api_key"] = os.getenv("GOOGLE_API_KEY") or None

    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_password = os.getenv("REDIS_PASSWORD") or None
    if redis_password:
        vals["redis_url"] = f"redis://:{redis_password}@{redis_host}:{redis_port}/0"
    else:
        vals["redis_url"] = f"redis://{redis_host}:{redis_port}/0"
    vals["redis_enabled"] = os.getenv("REDIS_ENABLED", "false").lower() == "true"

    channels_raw = os.getenv("REDIS_PUBSUB_CHANNELS", "")
    if channels_raw:
        vals["redis_pubsub_channels"] = [c.strip() for c in channels_raw.split(",")]

    session_path = os.getenv("SESSION_DB_PATH")
    if session_path:
        vals["session_db_path"] = session_path
    thread_path = os.getenv("THREAD_DB_PATH")
    if thread_path:
        vals["thread_db_path"] = thread_path
    canvas_path = os.getenv("CANVAS_DB_PATH")
    if canvas_path:
        vals["canvas_db_path"] = canvas_path

    audio_path = os.getenv("AUDIO_STORE_PATH")
    if audio_path:
        vals["audio_store_path"] = audio_path
    max_storage = os.getenv("AUDIO_MAX_STORAGE_GB")
    if max_storage:
        try:
            vals["audio_max_storage_gb"] = float(max_storage)
        except ValueError:
            pass

    backup_path = os.getenv("BACKUP_DIR")
    if backup_path:
        vals["backup_dir"] = backup_path
    interval = os.getenv("BACKUP_AUTO_INTERVAL_HOURS")
    if interval:
        try:
            vals["backup_auto_interval_hours"] = int(interval)
        except ValueError:
            pass
    keep = os.getenv("BACKUP_KEEP_COUNT")
    if keep:
        try:
            vals["backup_keep_count"] = int(keep)
        except ValueError:
            pass

    vals["jwt_secret"] = os.getenv("JWT_SECRET", "change-me")
    rate_limit = os.getenv("RATE_LIMIT_MAX")
    if rate_limit:
        try:
            vals["rate_limit_max"] = int(rate_limit)
        except ValueError:
            pass
    window = os.getenv("RATE_LIMIT_WINDOW")
    if window:
        try:
            vals["rate_limit_window"] = int(window)
        except ValueError:
            pass

    vals["calling_default_provider"] = os.getenv("CALLING_DEFAULT_PROVIDER", "webrtc")
    vals["calling_recording_enabled"] = os.getenv("CALLING_RECORDING_ENABLED", "false").lower() == "true"

    health_interval = os.getenv("HEALTH_CHECK_INTERVAL")
    if health_interval:
        try:
            vals["health_check_interval"] = int(health_interval)
        except ValueError:
            pass
    vals["metrics_enabled"] = os.getenv("METRICS_ENABLED", "true").lower() == "true"

    return SystemConfig(**vals)


def save_to_env(config: SystemConfig, path: Optional[str] = None) -> None:
    if path is None:
        path = str(ROOT_DIR / ".env")
    data = config.to_dict()
    lines = []
    mapping = {
        "log_level": "LOG_LEVEL",
        "tool_profile": "TOOL_PROFILE",
        "debug_mode": "DEBUG",
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "nvidia_api_key": "NVIDIA_API_KEY",
        "google_api_key": "GOOGLE_API_KEY",
        "redis_url": "REDIS_URL",
        "redis_enabled": "REDIS_ENABLED",
        "redis_pubsub_channels": "REDIS_PUBSUB_CHANNELS",
        "session_db_path": "SESSION_DB_PATH",
        "thread_db_path": "THREAD_DB_PATH",
        "canvas_db_path": "CANVAS_DB_PATH",
        "audio_store_path": "AUDIO_STORE_PATH",
        "audio_max_storage_gb": "AUDIO_MAX_STORAGE_GB",
        "backup_dir": "BACKUP_DIR",
        "backup_auto_interval_hours": "BACKUP_AUTO_INTERVAL_HOURS",
        "backup_keep_count": "BACKUP_KEEP_COUNT",
        "jwt_secret": "JWT_SECRET",
        "rate_limit_max": "RATE_LIMIT_MAX",
        "rate_limit_window": "RATE_LIMIT_WINDOW",
        "calling_default_provider": "CALLING_DEFAULT_PROVIDER",
        "calling_recording_enabled": "CALLING_RECORDING_ENABLED",
        "health_check_interval": "HEALTH_CHECK_INTERVAL",
        "metrics_enabled": "METRICS_ENABLED",
    }
    for key, env_name in mapping.items():
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            lines.append(f"{env_name}={str(value).lower()}")
        elif isinstance(value, list):
            lines.append(f"{env_name}={','.join(value)}")
        elif isinstance(value, float):
            lines.append(f"{env_name}={value}")
        else:
            lines.append(f"{env_name}={value}")
    with open(path, "w") as f:
        f.write("# PHI Agent Configuration — auto-generated\n")
        f.write("\n".join(lines) + "\n")
    logger.info("Configuration saved to %s", path)


system_config = load_from_env()
