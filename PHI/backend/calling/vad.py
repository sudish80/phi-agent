import logging
import struct
import asyncio
from typing import Optional, List, Tuple, Dict
from collections import deque

from backend.calling.models import VADConfig

logger = logging.getLogger(__name__)

try:
    import webrtcvad
    HAS_WEBRTCVAD = True
except ImportError:
    HAS_WEBRTCVAD = False
    logger.warning("webrtcvad not installed — VAD will use amplitude-only detection")


class NoiseGate:
    """Simple amplitude threshold filter before VAD processing."""

    def __init__(self, threshold: float = 0.02, sample_width: int = 2):
        self.threshold = threshold
        self.sample_width = sample_width

    def is_above_threshold(self, audio_bytes: bytes) -> bool:
        if not audio_bytes:
            return False
        fmt = "<" + "h" * (len(audio_bytes) // self.sample_width)
        try:
            samples = struct.unpack(fmt, audio_bytes[:len(audio_bytes) - len(audio_bytes) % self.sample_width])
        except (struct.error, ValueError):
            return False
        if not samples:
            return False
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        return rms > self.threshold * 32768


class VADProcessor:
    """Voice Activity Detection — wraps webrtcvad or uses amplitude stub."""

    def __init__(self, config: Optional[VADConfig] = None):
        self.config = config or VADConfig()
        self._vad = None
        if HAS_WEBRTCVAD:
            self._vad = webrtcvad.Vad(self.config.mode)
        self._noise_gate = NoiseGate(threshold=0.02)

    @property
    def sample_rate(self) -> int:
        return 16000

    @property
    def frame_size(self) -> int:
        return int(self.sample_rate * self.config.frame_ms / 1000) * 2

    def is_speech(self, audio_frame: bytes) -> bool:
        if not self._noise_gate.is_above_threshold(audio_frame):
            return False
        if self._vad:
            return self._vad.is_speech(audio_frame, self.sample_rate)
        return self._noise_gate.is_above_threshold(audio_frame)

    def process_chunk(self, audio_bytes: bytes) -> bool:
        if not self._noise_gate.is_above_threshold(audio_bytes):
            return False
        if self._vad:
            try:
                return self._vad.is_speech(audio_bytes, self.sample_rate)
            except Exception:
                return False
        return True

    def get_voice_segments(self, audio_bytes: bytes) -> List[Tuple[float, float]]:
        segments = []
        frame_len = self.frame_size
        total_frames = len(audio_bytes) // frame_len
        speaking = False
        seg_start = 0.0
        frame_duration_ms = self.config.frame_ms

        for i in range(total_frames):
            frame = audio_bytes[i * frame_len:(i + 1) * frame_len]
            is_speech_flag = self.process_chunk(frame)
            timestamp_ms = i * frame_duration_ms

            if is_speech_flag and not speaking:
                speaking = True
                seg_start = timestamp_ms
            elif not is_speech_flag and speaking:
                speaking = False
                segments.append((seg_start, timestamp_ms))

        if speaking:
            segments.append((seg_start, total_frames * frame_duration_ms))

        return segments


class VADManager:
    """Per-session VAD state tracking speaking/not-speaking transitions."""

    def __init__(self, session_id: str, config: Optional[VADConfig] = None):
        self.session_id = session_id
        self.config = config or VADConfig()
        self.processor = VADProcessor(self.config)
        self._is_speaking = False
        self._speech_buffer = deque(maxlen=50)
        self._transition_callbacks: List[callable] = []
        self._ambient_noise_level: float = 0.0
        self._ambient_samples: deque = deque(maxlen=100)

    def on_transition(self, callback: callable):
        self._transition_callbacks.append(callback)

    def _emit_transition(self, speaking: bool):
        for cb in self._transition_callbacks:
            try:
                cb(self.session_id, speaking)
            except Exception as e:
                logger.warning(f"Transition callback error: {e}")

    def feed_audio(self, audio_bytes: bytes) -> bool:
        is_speaking = self.processor.process_chunk(audio_bytes)
        self._speech_buffer.append(is_speaking)

        smoothed = sum(self._speech_buffer) / len(self._speech_buffer) > 0.5

        if smoothed != self._is_speaking:
            self._is_speaking = smoothed
            self._emit_transition(smoothed)

        return smoothed

    def is_currently_speaking(self) -> bool:
        return self._is_speaking

    def update_ambient_noise(self, audio_bytes: bytes):
        if not audio_bytes:
            return
        fmt = "<" + "h" * (len(audio_bytes) // 2)
        try:
            samples = struct.unpack(fmt, audio_bytes[:len(audio_bytes) - len(audio_bytes) % 2])
        except (struct.error, ValueError):
            return
        if not samples:
            return
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
        self._ambient_samples.append(rms)
        if len(self._ambient_samples) > 10:
            self._ambient_noise_level = sum(self._ambient_samples) / len(self._ambient_samples)
            self._auto_tune_threshold()

    def _auto_tune_threshold(self):
        base = self._ambient_noise_level / 32768
        new_threshold = min(base * 2.5, 0.5)
        self.processor._noise_gate.threshold = max(new_threshold, 0.01)
        logger.debug(f"Auto-tuned VAD threshold to {self.processor._noise_gate.threshold:.4f}")


class VADRegistry:
    """Registry of per-session VAD managers."""

    def __init__(self):
        self._managers: Dict[str, VADManager] = {}

    def get_or_create(self, session_id: str, config: Optional[VADConfig] = None) -> VADManager:
        if session_id not in self._managers:
            self._managers[session_id] = VADManager(session_id, config)
        return self._managers[session_id]

    def remove(self, session_id: str):
        self._managers.pop(session_id, None)

    def get(self, session_id: str) -> Optional[VADManager]:
        return self._managers.get(session_id)


vad_registry = VADRegistry()
