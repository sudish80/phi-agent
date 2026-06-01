"""Hearing Service — microphone capture, VAD, Whisper STT, wake word.

FastAPI endpoints:
  - POST /transcribe: audio file → text
  - WS /hear: streaming audio → streaming transcription
  - GET /status: service health
"""

import asyncio
import base64
import json
import logging
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from pydantic import BaseModel

from backend.shared.config import settings
from backend.shared.redis_client import RedisPubSub
from backend.hearing.stt import stt
from backend.hearing.mic_stream import mic

logger = logging.getLogger(__name__)

app = FastAPI(title="PHI Hearing Service", version="1.0.0")
redis = RedisPubSub()


class TranscribeRequest(BaseModel):
    audio: str  # base64-encoded WAV
    language: str = "en"


class TranscribeResponse(BaseModel):
    text: str
    language: str = "en"
    confidence: float = 0.0
    duration: float = 0.0
    is_wake_word: bool = False


# Wake word detection (simple keyword spotting)
WAKE_WORDS = [settings.phi_wake_word.lower(), "hey phi", "ok phi"]


def check_wake_word(text: str) -> bool:
    text_lower = text.lower().strip()
    return any(ww in text_lower for ww in WAKE_WORDS)


@app.on_event("startup")
async def startup():
    await redis.connect("hearing")
    stt.load_model()

    mic.set_on_utterance(on_utterance)

    # Subscribe to RPC channel
    async def handle_rpc(msg):
        if msg.payload.get("method") == "transcribe":
            audio_data = base64.b64decode(msg.payload.get("params", {}).get("audio", ""))
            result = await stt.transcribe(audio_data)
            response_channel = msg.payload.get("_response_channel")
            if response_channel:
                await redis.publish(response_channel, {
                    "status": "ok",
                    "data": result,
                })

    redis.subscribe("rpc:hearing", handle_rpc)
    await redis.start_listening()


def on_utterance(audio_bytes: bytes):
    """Called when a complete utterance is detected."""
    asyncio.ensure_future(process_utterance(audio_bytes))


async def process_utterance(audio_bytes: bytes):
    try:
        result = await stt.transcribe(audio_bytes)
        text = result.get("text", "").strip()
        if not text:
            return

        is_wake = check_wake_word(text)

        logger.info(f"Transcribed: '{text}' (wake={is_wake})")

        await redis.publish("hearing:transcription", {
            "text": text,
            "confidence": result.get("confidence", 0),
            "is_wake_word": is_wake,
            "timestamp": time.time(),
        })

        if is_wake:
            clean_text = text.lower()
            for ww in WAKE_WORDS:
                clean_text = clean_text.replace(ww, "").strip()
            if not clean_text:
                return
            await redis.publish("hearing:wake_word", {
                "text": clean_text,
                "confidence": result.get("confidence", 0),
                "timestamp": time.time(),
            })

    except Exception as e:
        logger.error(f"Error processing utterance: {e}")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "hearing",
        "mic_running": mic._running if hasattr(mic, '_running') else False,
        "is_speaking": mic.is_speaking(),
    }


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_endpoint(request: TranscribeRequest):
    audio_bytes = base64.b64decode(request.audio)
    result = await stt.transcribe(audio_bytes)
    text = result.get("text", "").strip()
    return TranscribeResponse(
        text=text,
        language=result.get("language", "en"),
        confidence=result.get("confidence", 0),
        duration=result.get("duration", 0),
        is_wake_word=check_wake_word(text),
    )


@app.post("/transcribe-file")
async def transcribe_file(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = await stt.transcribe(audio_bytes)
    return {
        "text": result.get("text", "").strip(),
        "filename": file.filename,
        "confidence": result.get("confidence", 0),
    }


@app.get("/is-speaking")
async def is_speaking():
    return {"speaking": mic.is_speaking()}


@app.get("/buffer")
async def get_buffer():
    buf = mic.get_buffer(5.0)
    return {
        "buffer_size": len(buf),
        "sample_rate": 16000,
    }


@app.websocket("/hear")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Hearing WebSocket connected")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            audio_b64 = msg.get("audio", "")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                result = await stt.transcribe(audio_bytes)
                await websocket.send_json({
                    "text": result.get("text", "").strip(),
                    "confidence": result.get("confidence", 0),
                    "is_final": True,
                })
    except WebSocketDisconnect:
        logger.info("Hearing WebSocket disconnected")
    except Exception as e:
        logger.error(f"Hearing WebSocket error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level))
    uvicorn.run("backend.hearing.service:app", host="0.0.0.0", port=settings.hearing_port)
