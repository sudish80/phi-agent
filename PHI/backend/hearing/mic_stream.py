"""Microphone capture with WebRTC Voice Activity Detection (VAD).

Always-on capture with silence-based segmentation.
"""

import io
import wave
import struct
import logging
import threading
import time
import collections
from typing import Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from backend.shared.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    data: bytes
    timestamp: float
    duration_ms: float
    is_speech: bool = False
    sample_rate: int = 16000


class AudioRingBuffer:
    """Ring buffer for storing recent audio chunks."""

    def __init__(self, max_duration_sec: int = 30, sample_rate: int = 16000):
        self.max_samples = max_duration_sec * sample_rate
        self.sample_rate = sample_rate
        self._buffer: List[float] = []
        self._lock = threading.Lock()

    def add(self, audio_array: np.ndarray):
        with self._lock:
            self._buffer.extend(audio_array.tolist())
            if len(self._buffer) > self.max_samples:
                self._buffer = self._buffer[-self.max_samples:]

    def get_recent(self, duration_sec: float = 5.0) -> np.ndarray:
        n_samples = int(duration_sec * self.sample_rate)
        with self._lock:
            recent = self._buffer[-n_samples:] if len(self._buffer) > n_samples else self._buffer
            return np.array(recent, dtype=np.float32)

    def clear(self):
        with self._lock:
            self._buffer.clear()

    def __len__(self):
        with self._lock:
            return len(self._buffer)


class MicrophoneStream:
    """Always-on microphone capture with VAD-based segmentation.

    Captures audio in a background thread, detects voice activity,
    segments speech into utterances, and notifies listeners.
    """

    def __init__(self):
        self._stream = None
        self._audio_interface = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._vad = None
        self._ring_buffer = AudioRingBuffer()
        self._speech_buffer: List[bytes] = []
        self._silence_duration = 0.0
        self._is_speaking = False
        self._on_speech_detected: Optional[Callable] = None
        self._on_utterance_complete: Optional[Callable[[bytes], None]] = None
        self._sample_rate = 16000
        self._channels = 1
        self._sample_width = 2  # 16-bit
        self._chunk_duration_ms = 30
        self._chunk_size = int(self._sample_rate * self._chunk_duration_ms / 1000)

    def start(self):
        if self._running:
            return
        try:
            import pyaudio
            self._audio_interface = pyaudio.PyAudio()
            self._stream = self._audio_interface.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._chunk_size,
                stream_callback=self._audio_callback,
            )
            self._vad = self._create_vad()
            self._running = True
            self._stream.start_stream()
            logger.info("Microphone capture started")
        except Exception as e:
            logger.error(f"Failed to start mic: {e}")
            self._use_mock()

    def _create_vad(self):
        try:
            import webrtcvad
            vad = webrtcvad.Vad()
            vad.set_mode(int(settings.vad_threshold * 3))
            return vad
        except ImportError:
            logger.warning("webrtcvad not installed, using simple energy VAD")
            return None

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback - runs in audio thread."""
        if not self._running:
            return (None, pyaudio.paComplete)

        is_speech = self._is_speech_frame(in_data)

        self._ring_buffer.add(np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0)

        if is_speech:
            self._speech_buffer.append(in_data)
            self._silence_duration = 0.0
            if not self._is_speaking:
                self._is_speaking = True
                if self._on_speech_detected:
                    self._on_speech_detected()
        else:
            self._silence_duration += self._chunk_duration_ms / 1000.0
            if self._is_speaking and self._silence_duration > (settings.vad_min_silence_ms / 1000.0):
                self._is_speaking = False
                utterance = b"".join(self._speech_buffer)
                self._speech_buffer.clear()
                if len(utterance) > 800:  # Minimum utterance size
                    if self._on_utterance_complete:
                        self._on_utterance_complete(utterance)

        return (None, pyaudio.paContinue)

    def _is_speech_frame(self, audio_bytes: bytes) -> bool:
        if self._vad:
            try:
                return self._vad.is_speech(audio_bytes, self._sample_rate)
            except Exception:
                pass
        return self._energy_vad(audio_bytes)

    def _energy_vad(self, audio_bytes: bytes) -> bool:
        samples = struct.unpack_from(f"<{len(audio_bytes) // 2}h", audio_bytes)
        energy = sum(abs(s) for s in samples) / len(samples)
        return energy > 500

    def _use_mock(self):
        logger.info("Using mock microphone")
        self._running = True
        self._thread = threading.Thread(target=self._mock_loop, daemon=True)
        self._thread.start()

    def _mock_loop(self):
        import struct
        import math
        freq = 440
        while self._running:
            samples = [int(32767 * 0.3 * math.sin(2 * math.pi * freq * t / self._sample_rate))
                       for t in range(self._chunk_size)]
            data = struct.pack(f"<{len(samples)}h", *samples)
            self._ring_buffer.add(np.array(samples, dtype=np.float32) / 32768.0)
            time.sleep(self._chunk_duration_ms / 1000.0)

    def set_on_speech(self, callback: Callable):
        self._on_speech_detected = callback

    def set_on_utterance(self, callback: Callable[[bytes], None]):
        self._on_utterance_complete = callback

    def get_buffer(self, duration_sec: float = 5.0) -> np.ndarray:
        return self._ring_buffer.get_recent(duration_sec)

    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._audio_interface:
            self._audio_interface.terminate()
        logger.info("Microphone capture stopped")


mic = MicrophoneStream()
