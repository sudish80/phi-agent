"""Text-to-speech engine with human-like prosody, emotion, and lip sync.

Features:
  - Multi-engine: ElevenLabs (primary), Coqui TTS (local fallback)
  - 8 emotions: neutral, happy, serious, excited, calm, angry, sad, whisper
  - Human-like speech: filler words, varied pacing, natural pauses
  - Viseme generation for avatar lip sync
  - TTS caching for common phrases
  - Interruption support
"""

import os
import io
import json
import base64
import hashlib
import logging
import asyncio
import random
import time
import re
from typing import Dict, Any, Optional, List, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import OrderedDict
from io import BytesIO

from backend.shared.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Human-like speech processing
# ============================================================

# Filler phrases for natural speech
FILLERS = {
    "neutral": [],
    "happy": ["you know", "actually", "honestly", "I gotta say"],
    "excited": ["oh wow", "I mean", "seriously", "check this out"],
    "calm": ["you see", "well", "now", "of course"],
    "serious": ["look", "the thing is", "here's the deal"],
}

# Speech rate modifiers per emotion (1.0 = normal)
EMOTION_RATES = {
    "neutral": 1.0,
    "happy": 1.1,
    "serious": 0.85,
    "excited": 1.2,
    "calm": 0.8,
    "angry": 1.15,
    "sad": 0.75,
    "whisper": 0.7,
}

# Pitch modifiers per emotion (semitones)
EMOTION_PITCH = {
    "neutral": 0,
    "happy": 2,
    "serious": -1,
    "excited": 3,
    "calm": -1,
    "angry": 1,
    "sad": -2,
    "whisper": -1,
}


def humanize_text(text: str, emotion: str = "neutral") -> str:
    """Add human-like qualities to TTS text.

    Inserts natural pauses, varied phrasing, and emotion-appropriate
    filler words to make speech sound less robotic.
    """
    if not text:
        return text

    text = text.strip()

    if emotion == "whisper":
        text = text.lower()

    if random.random() < 0.15 and emotion in FILLERS and FILLERS[emotion]:
        filler = random.choice(FILLERS[emotion])
        if random.random() < 0.5:
            text = f"{filler.capitalize()}, {text[0].lower()}{text[1:]}"
        else:
            text = f"{text}, {filler}"

    text = re.sub(r'\.( +)', lambda m: '.' + random.choice(['. ', '... ', '.. ']), text)

    end_char = text[-1] if text else ''
    if end_char not in ('.', '!', '?', ':', ';', ',', '...'):
        text += '.'

    return text


def apply_voice_effect(text: str, effect: str = "none") -> str:
    """Apply voice effect to text via preprocessing."""
    if effect == "none" or not effect:
        return text
    effect = effect.lower()
    if effect == "radio":
        return f"[radio static] {text} [radio static]"
    elif effect == "echo":
        words = text.split()
        result = []
        for w in words:
            result.append(w)
            if random.random() < 0.2:
                result.append("..." + w)
        return " ".join(result)
    elif effect == "robotic":
        words = text.split()
        return " ".join(f"{w}... " if i % 3 == 2 else w for i, w in enumerate(words))
    elif effect == "whisper":
        return f"[whispering] {text.lower()} [/whispering]"
    elif effect == "slow":
        words = text.split()
        return "... ".join(words)
    elif effect == "fast":
        return text.upper()
    return text


@dataclass
class Viseme:
    """A viseme (visual mouth shape) for lip sync animation."""
    phoneme: str
    start_time: float
    end_time: float
    shape: str = "rest"  # rest, A, E, I, O, U, M, F, L, etc.

    VISEME_MAP = {
        'AA': 'A', 'AE': 'A', 'AH': 'A', 'AO': 'O',
        'AW': 'O', 'AY': 'I',
        'B': 'M', 'M': 'M', 'P': 'M',
        'CH': 'F', 'JH': 'F', 'SH': 'F', 'ZH': 'F',
        'D': 'L', 'N': 'L', 'T': 'L', 'S': 'L', 'Z': 'L',
        'DH': 'L', 'TH': 'L',
        'EH': 'E', 'ER': 'E',
        'EY': 'I',
        'F': 'F', 'V': 'F',
        'G': 'L', 'K': 'L', 'NG': 'L', 'HH': 'L',
        'IH': 'I', 'IY': 'I',
        'OW': 'O', 'OY': 'O',
        'R': 'L', 'Y': 'L', 'W': 'O',
        'UH': 'U', 'UW': 'U',
    }

    @classmethod
    def from_phoneme(cls, phoneme: str, start: float, end: float) -> 'Viseme':
        base = re.sub(r'\d', '', phoneme.upper())
        shape = cls.VISEME_MAP.get(base, 'L' if base else 'rest')
        return cls(phoneme=phoneme, start_time=start, end_time=end, shape=shape)


# ============================================================
# TTS Engine
# ============================================================

class TTSEngine:
    """Multi-engine TTS with human-like speech, emotion, and caching.

    Primary: ElevenLabs API (with emotion + speed control)
    Fallback: Coqui TTS (local)
    Last resort: gTTS
    """

    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._cache_order: List[str] = []
        self._cache_max = 200
        self._coqui = None
        self._coqui_loaded = False
        self._current_utterance: Optional[asyncio.Task] = None
        self._interrupted = False

    def _cache_key(self, text: str, emotion: str, voice: str) -> str:
        raw = f"{text}:{emotion}:{voice}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[bytes]:
        if key in self._cache:
            self._cache_order.remove(key)
            self._cache_order.append(key)
            logger.debug(f"TTS cache hit: {key[:8]}")
            return self._cache[key]["audio"]
        return None

    def _add_to_cache(self, key: str, audio: bytes, visemes: list):
        if len(self._cache) >= self._cache_max:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = {"audio": audio, "visemes": visemes}
        self._cache_order.append(key)

    async def synthesize(self, text: str, emotion: str = "neutral",
                         return_visemes: bool = True,
                         rate: float = 1.0, pitch: float = 0.0,
                         effect: str = "none") -> Dict[str, Any]:
        """Synthesize text to audio with emotion and human-like qualities.

        Args:
            text: Text to synthesize
            emotion: Emotional tone
            return_visemes: Whether to include viseme data
            rate: Speech rate multiplier (0.5-2.0, default 1.0)
            pitch: Pitch shift in semitones (default 0)
            effect: Voice effect (none, radio, echo, robotic, whisper, slow, fast)
        """
        start = time.time()
        effect = effect or "none"

        text = humanize_text(text, emotion)
        text = apply_voice_effect(text, effect)
        rate = max(0.5, min(2.0, rate))
        pitch = max(-12, min(12, pitch))

        voice_id = settings.tts_voice_id
        cache_key = self._cache_key(text, emotion, voice_id)

        cached = self._get_from_cache(cache_key) if settings.tts_cache_enabled else None
        if cached:
            visemes = self._generate_visemes(text, cached, emotion)
            return {
                "audio": base64.b64encode(cached).decode("utf-8"),
                "audio_format": "mp3",
                "visemes": visemes if return_visemes else [],
                "emotion": emotion,
                "duration_ms": self._estimate_duration_ms(text, emotion),
                "cache_hit": True,
                "latency_ms": (time.time() - start) * 1000,
                "rate": rate,
                "pitch": pitch,
                "effect": effect,
            }

        audio_data = None
        visemes = []

        if settings.elevenlabs_api_key and not self._interrupted:
            audio_data = await self._synthesize_elevenlabs(text, emotion, rate)
            if audio_data:
                visemes = self._generate_visemes(text, audio_data, emotion)
                self._add_to_cache(cache_key, audio_data, visemes)

        if not audio_data and not self._interrupted:
            audio_data = await self._synthesize_coqui(text, emotion)
            if audio_data:
                visemes = self._generate_visemes(text, audio_data, emotion)

        if not audio_data and not self._interrupted:
            audio_data = await self._synthesize_gtts(text)
            if audio_data:
                visemes = self._generate_visemes(text, audio_data, emotion)

        if not audio_data:
            return {"error": "All TTS engines failed", "text": text}

        audio_data = self._apply_audio_eq(audio_data, effect, rate, pitch)
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        duration_ms = self._estimate_duration_ms(text, emotion)

        return {
            "audio": audio_b64,
            "audio_format": "mp3",
            "visemes": visemes if return_visemes else [],
            "emotion": emotion,
            "duration_ms": duration_ms,
            "cache_hit": False,
            "latency_ms": (time.time() - start) * 1000,
            "rate": rate,
            "pitch": pitch,
            "effect": effect,
        }

    async def _synthesize_elevenlabs(self, text: str, emotion: str,
                                      rate: float = 1.0) -> Optional[bytes]:
        import aiohttp
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.tts_voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.elevenlabs_api_key,
        }

        stability = 0.3 if emotion in ("excited", "happy") else 0.5
        similarity = 0.7 if emotion in ("serious", "sad") else 0.5
        speed = min(1.5, max(0.5, rate))

        payload = {
            "text": text,
                "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity,
                "style": 0.3 if emotion != "neutral" else 0.0,
                "use_speaker_boost": True,
                "speed": speed,
            },
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        logger.info(f"ElevenLabs TTS: {len(audio_data)} bytes")
                        return audio_data
                    else:
                        error_text = await resp.text()
                        logger.warning(f"ElevenLabs error {resp.status}: {error_text[:200]}")
                        return None
            except Exception as e:
                logger.warning(f"ElevenLabs request failed: {e}")
                return None

    async def _synthesize_coqui(self, text: str, emotion: str) -> Optional[bytes]:
        try:
            if not self._coqui_loaded:
                from TTS.api import TTS
                model_name = settings.tts_local_model
                self._coqui = TTS(model_name=model_name, progress_bar=False, gpu=False)
                self._coqui_loaded = True
                logger.info(f"Coqui TTS loaded: {model_name}")

            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                output_path = tmp.name

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._coqui.tts_to_file(
                    text=text,
                    file_path=output_path,
                    speed=EMOTION_RATES.get(emotion, 1.0),
                )
            )

            with open(output_path, "rb") as f:
                audio_data = f.read()
            os.unlink(output_path)
            return audio_data

        except Exception as e:
            logger.warning(f"Coqui TTS failed: {e}")
            return None

    async def _synthesize_gtts(self, text: str) -> Optional[bytes]:
        try:
            from gtts import gTTS
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                output_path = tmp.name

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: gTTS(text=text, lang="en", slow=False).save(output_path),
            )

            with open(output_path, "rb") as f:
                audio_data = f.read()
            os.unlink(output_path)
            return audio_data
        except Exception as e:
            logger.warning(f"gTTS failed: {e}")
            return None

    def _generate_visemes(self, text: str, audio_bytes: bytes,
                           emotion: str) -> List[Dict]:
        """Generate viseme timestamps for lip sync animation.

        Uses estimated phoneme durations based on text length and audio duration.
        """
        import numpy as np

        if not text or not audio_bytes:
            return []

        duration_ms = self._estimate_duration_ms(text, emotion)

        words = text.split()
        if not words:
            return []

        avg_word_duration = duration_ms / len(words)
        visemes = []
        current_time = 0.0

        for word in words:
            word_duration = max(avg_word_duration * (len(word) / 5), 80)

            for i, char in enumerate(word.lower()):
                char_duration = word_duration / len(word)

                if char in 'aeiou':
                    if char == 'a':
                        shape = 'A'
                    elif char == 'e':
                        shape = 'E'
                    elif char == 'i':
                        shape = 'I'
                    elif char == 'o':
                        shape = 'O'
                    elif char == 'u':
                        shape = 'U'
                    else:
                        shape = 'L'
                elif char in 'bfmp':
                    shape = 'M'
                elif char in 'fv':
                    shape = 'F'
                elif char in 'szlndtr':
                    shape = 'L'
                elif char in 'w':
                    shape = 'O'
                elif char in 'kg':
                    shape = 'L'
                else:
                    shape = 'rest'

                visemes.append({
                    "shape": shape,
                    "start_ms": current_time,
                    "end_ms": current_time + char_duration,
                    "phoneme": char,
                })
                current_time += char_duration

            current_time += 30

        return visemes[:200]

    def _apply_audio_eq(self, audio_bytes: bytes, effect: str = "none",
                         rate: float = 1.0, pitch: float = 0.0) -> bytes:
        """Apply real audio EQ using pydub — frequency-based processing."""
        if effect == "none" and rate == 1.0 and pitch == 0:
            return audio_bytes
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(BytesIO(audio_bytes))
            if rate != 1.0:
                audio = audio.speedup(playback_speed=rate) if rate > 1.0 else audio._spawn(audio.raw_data, overrides={"frame_rate": int(audio.frame_rate * rate)}).set_frame_rate(audio.frame_rate)
            if effect == "bass_boost":
                audio = audio.low_pass_filter(250).apply_gain(6) + audio.high_pass_filter(250)
            elif effect == "bass_cut":
                audio = audio.high_pass_filter(250)
            elif effect == "treble_boost":
                audio = audio.high_pass_filter(4000).apply_gain(6) + audio.low_pass_filter(4000)
            elif effect == "treble_cut":
                audio = audio.low_pass_filter(4000)
            elif effect == "voice_clarity":
                audio = audio.high_pass_filter(300).low_pass_filter(4000).apply_gain(3)
            elif effect == "loudness":
                from pydub.effects import normalize
                audio = normalize(audio)
            elif effect == "telephone":
                audio = audio.low_pass_filter(3500).high_pass_filter(300).apply_gain(2)
            elif effect == "deep":
                audio = audio.low_pass_filter(150).apply_gain(4) + audio.high_pass_filter(150).apply_gain(-2)
            buf = BytesIO()
            audio.export(buf, format="mp3", bitrate="64k")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Audio EQ failed: {e}")
            return audio_bytes

    def _estimate_duration_ms(self, text: str, emotion: str = "neutral") -> float:
        """Estimate audio duration in milliseconds based on text length and emotion rate."""
        char_count = len(text)
        rate = EMOTION_RATES.get(emotion, 1.0)
        base_duration = (char_count / 15.0) * 1000
        return base_duration / rate

    def interrupt(self):
        """Interrupt current TTS playback."""
        self._interrupted = True
        if self._current_utterance and not self._current_utterance.done():
            self._current_utterance.cancel()
        logger.info("TTS interrupted")

    def clear_cache(self):
        self._cache.clear()
        self._cache_order.clear()
        logger.info("TTS cache cleared")

tts = TTSEngine()
PhiTTS = TTSEngine

