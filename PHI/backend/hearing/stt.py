"""Speech-to-text using Whisper (local or API)."""

import io
import wave
import base64
import logging
import numpy as np
from typing import Optional, Dict, Any

from backend.shared.config import settings

logger = logging.getLogger(__name__)


class WhisperSTT:
    """Speech-to-text using OpenAI Whisper (local tiny model or API)."""

    def __init__(self):
        self._model = None
        self._use_api = False
        self._model_loaded = False

    def load_model(self):
        if self._model_loaded:
            return
        try:
            import whisper
            self._model = whisper.load_model(settings.whisper_model)
            self._model_loaded = True
            logger.info(f"Whisper model '{settings.whisper_model}' loaded locally")
        except Exception as e:
            logger.warning(f"Local Whisper unavailable, will use API: {e}")
            self._use_api = True
            self._model_loaded = True

    async def transcribe(self, audio_data: bytes) -> Dict[str, Any]:
        """Transcribe audio bytes to text."""
        self.load_model()
        try:
            if self._use_api:
                return await self._transcribe_api(audio_data)
            else:
                return await self._transcribe_local(audio_data)
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {"text": "", "error": str(e), "language": "unknown"}

    async def _transcribe_local(self, audio_data: bytes) -> Dict[str, Any]:
        import whisper
        audio_array = self._bytes_to_numpy(audio_data)
        result = self._model.transcribe(
            audio_array,
            language="en",
            task="transcribe",
            fp16=False,
        )
        return {
            "text": result.get("text", "").strip(),
            "language": result.get("language", "en"),
            "segments": result.get("segments", []),
            "confidence": max((s.get("confidence", 0) for s in result.get("segments", [])), default=0),
            "duration": result.get("segments", [{}])[-1].get("end", 0) if result.get("segments") else 0,
        }

    async def _transcribe_api(self, audio_data: bytes) -> Dict[str, Any]:
        import aiohttp
        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("file", audio_file, filename="audio.wav", content_type="audio/wav")
            form.add_field("model", "whisper-1")
            form.add_field("response_format", "verbose_json")

            async with session.post(url, headers=headers, data=form) as resp:
                if resp.status != 200:
                    return {"text": "", "error": f"API error: {resp.status}"}
                data = await resp.json()
                return {
                    "text": data.get("text", "").strip(),
                    "language": data.get("language", "en"),
                    "segments": data.get("segments", []),
                    "confidence": data.get("segments", [{}])[0].get("confidence", 0) if data.get("segments") else 0,
                    "duration": data.get("duration", 0),
                }

    def _bytes_to_numpy(self, audio_data: bytes) -> np.ndarray:
        """Convert WAV bytes to numpy array for Whisper."""
        try:
            with io.BytesIO(audio_data) as buf:
                with wave.open(buf, "rb") as wf:
                    frames = wf.readframes(wf.getnframes())
                    dtype = np.int16 if wf.getsampwidth() == 2 else np.int32
                    audio_array = np.frombuffer(frames, dtype=dtype).astype(np.float32) / 32768.0
                    return audio_array
        except Exception:
            return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    async def transcribe_file(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "rb") as f:
            return await self.transcribe(f.read())


stt = WhisperSTT()


async def transcribe_audio(audio_bytes: bytes) -> str:
    result = await stt.transcribe(audio_bytes)
    return result.get("text", "")
