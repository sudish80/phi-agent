import logging
import os
import uuid
from abc import ABC, abstractmethod
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "workspace",
    "audio",
)


class AudioProcessor(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def text_to_speech(self, text: str, output_path: Optional[str] = None) -> str:
        ...

    @abstractmethod
    def speech_to_text(self, audio_path: str) -> str:
        ...

    def get_name(self) -> str:
        return self.name


class DummyAudioProcessor(AudioProcessor):
    def __init__(self, audio_dir: str = DEFAULT_AUDIO_DIR):
        super().__init__("dummy")
        self.audio_dir = audio_dir
        os.makedirs(self.audio_dir, exist_ok=True)

    def text_to_speech(self, text: str, output_path: Optional[str] = None) -> str:
        file_path = output_path or os.path.join(self.audio_dir, f"tts_{uuid.uuid4().hex[:12]}.wav")
        logger.info("Dummy TTS: '%s' -> %s", text[:60], file_path)
        with open(file_path, "w") as f:
            f.write(f"DUMMY_TTS:{text}")
        return file_path

    def speech_to_text(self, audio_path: str) -> str:
        logger.info("Dummy STT from: %s", audio_path)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        try:
            with open(audio_path, "r") as f:
                content = f.read()
            if content.startswith("DUMMY_TTS:"):
                return content[len("DUMMY_TTS:"):]
            return f"[transcribed text from {os.path.basename(audio_path)}]"
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Could not read dummy audio: %s", e)
            return f"[transcription of {os.path.basename(audio_path)}]"


class AudioRegistry:
    def __init__(self):
        self._processors: dict[str, AudioProcessor] = {}
        self._lock = Lock()
        self._register_defaults()

    def _register_defaults(self):
        self.register(DummyAudioProcessor())

    def register(self, processor: AudioProcessor, overwrite: bool = False):
        with self._lock:
            if processor.name in self._processors and not overwrite:
                raise ValueError(f"Audio processor '{processor.name}' already registered")
            self._processors[processor.name] = processor
            logger.info("Registered audio processor '%s'", processor.name)

    def unregister(self, name: str):
        with self._lock:
            self._processors.pop(name, None)
            logger.info("Unregistered audio processor '%s'", name)

    def get(self, name: str = "dummy") -> Optional[AudioProcessor]:
        with self._lock:
            return self._processors.get(name)

    def list_processors(self) -> list[str]:
        with self._lock:
            return list(self._processors.keys())


_registry = AudioRegistry()


def text_to_speech(text: str, processor: str = "dummy", output_path: Optional[str] = None) -> str:
    proc = _registry.get(processor)
    if proc is None:
        raise ValueError(f"Unknown audio processor '{processor}'. Available: {_registry.list_processors()}")
    return proc.text_to_speech(text, output_path=output_path)


def speech_to_text(audio_path: str, processor: str = "dummy") -> str:
    proc = _registry.get(processor)
    if proc is None:
        raise ValueError(f"Unknown audio processor '{processor}'. Available: {_registry.list_processors()}")
    return proc.speech_to_text(audio_path)


def get_audio_registry() -> AudioRegistry:
    return _registry
