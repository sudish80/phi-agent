"""Global configuration for PHI Agent.

Loads settings from environment variables with sensible defaults.
Uses pydantic-settings for validation and type coercion.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import lru_cache

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self._load()

    def _load(self):
        # Core
        self.user_name: str = os.getenv("USER_NAME", "User")
        self.phi_wake_word: str = os.getenv("PHI_WAKE_WORD", "phi")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.debug: bool = os.getenv("DEBUG", "true").lower() == "true"

        # API Keys
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
        self.openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.elevenlabs_api_key: Optional[str] = os.getenv("ELEVENLABS_API_KEY")
        self.serpapi_api_key: Optional[str] = os.getenv("SERPAPI_API_KEY")
        self.weather_api_key: Optional[str] = os.getenv("WEATHER_API_KEY")
        self.nvidia_api_key: Optional[str] = os.getenv("NVIDIA_API_KEY")

        # Redis
        self.redis_host: str = os.getenv("REDIS_HOST", "localhost")
        self.redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password: Optional[str] = os.getenv("REDIS_PASSWORD") or None

        # ChromaDB
        self.chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
        self.chroma_port: int = int(os.getenv("CHROMA_PORT", "8000"))
        self.chroma_collection: str = os.getenv("CHROMA_COLLECTION", "phi_memory")

        # MQTT
        self.mqtt_broker: str = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port: int = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username: Optional[str] = os.getenv("MQTT_USERNAME")
        self.mqtt_password: Optional[str] = os.getenv("MQTT_PASSWORD")

        # Email
        self.email_address: Optional[str] = os.getenv("EMAIL_ADDRESS")
        self.email_password: Optional[str] = os.getenv("EMAIL_PASSWORD")
        self.smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))

        # Service ports
        self.orchestrator_port: int = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
        self.vision_port: int = int(os.getenv("VISION_PORT", "8001"))
        self.hearing_port: int = int(os.getenv("HEARING_PORT", "8002"))
        self.speech_port: int = int(os.getenv("SPEECH_PORT", "8003"))
        self.action_port: int = int(os.getenv("ACTION_PORT", "8004"))

        # Vision
        self.camera_index: int = int(os.getenv("CAMERA_INDEX", "0"))
        self.camera_rtsp_url: Optional[str] = os.getenv("CAMERA_RTSP_URL") or None
        self.detection_interval: float = float(os.getenv("DETECTION_INTERVAL", "0.1"))
        self.face_recognition_enabled: bool = os.getenv("FACE_RECOGNITION_ENABLED", "true").lower() == "true"

        # Hearing
        self.mic_index: int = int(os.getenv("MIC_INDEX", "0"))
        self.vad_threshold: float = float(os.getenv("VAD_THRESHOLD", "0.5"))
        self.vad_min_silence_ms: int = int(os.getenv("VAD_MIN_SILENCE_MS", "500"))
        self.whisper_model: str = os.getenv("WHISPER_MODEL", "tiny")
        self.wake_word_sensitivity: float = float(os.getenv("WAKE_WORD_SENSITIVITY", "0.5"))

        # Speech
        self.tts_engine: str = os.getenv("TTS_ENGINE", "elevenlabs")
        self.tts_voice_id: str = os.getenv("TTS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.tts_local_model: str = os.getenv("TTS_LOCAL_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
        self.tts_cache_enabled: bool = os.getenv("TTS_CACHE_ENABLED", "true").lower() == "true"

        # LLM
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4")
        self.local_llm_url: str = os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1")
        self.local_llm_model: str = os.getenv("LOCAL_LLM_MODEL", "llama-3-70b")
        self.max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
        self.temperature: float = float(os.getenv("TEMPERATURE", "0.7"))

        # Memory Palace
        self.memory_palace_enabled: bool = os.getenv("MEMORY_PALACE_ENABLED", "true").lower() == "true"
        self.memory_palace_rooms: int = int(os.getenv("MEMORY_PALACE_ROOMS", "20"))
        self.memory_dimension: int = int(os.getenv("MEMORY_DIMENSION", "1536"))
        self.memory_top_k: int = int(os.getenv("MEMORY_TOP_K", "5"))
        self.memory_backend: str = os.getenv("MEMORY_BACKEND", "chromadb")

    @property
    def chroma_url(self) -> str:
        return f"http://{self.chroma_host}:{self.chroma_port}"

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    def dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def __repr__(self) -> str:
        return f"Settings(user_name={self.user_name}, llm={self.llm_provider}/{self.llm_model})"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
