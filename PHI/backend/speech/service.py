"""Speech Service — TTS with emotion, human-like speech, and lip sync.

FastAPI endpoints:
  - POST /synthesize: text + emotion → base64 audio + visemes
  - WS /talk: streaming text → streaming audio chunks
  - GET /voices: list available voices
  - POST /interrupt: stop current TTS
  - GET /metrics: audio quality and usage metrics
"""

import asyncio
import json
import logging
import time
import base64
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel

from backend.shared.config import settings
from backend.shared.redis_client import RedisPubSub
from backend.speech.tts_engine import tts
from backend.speech.lip_sync import lip_sync_gen

logger = logging.getLogger(__name__)

app = FastAPI(title="J.A.R.V.I.S. Speech Service", version="1.0.0")
redis = RedisPubSub()

# Metrics tracking
_metrics = {
    "total_synthesize_calls": 0,
    "total_characters": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "errors": 0,
    "engines_used": {},
    "emotions_used": {},
    "effects_used": {},
    "avg_duration_ms": 0.0,
    "avg_latency_ms": 0.0,
    "start_time": time.time(),
}


class SynthesizeRequest(BaseModel):
    text: str
    emotion: str = "neutral"
    return_visemes: bool = True
    humanize: bool = True
    rate: float = 1.0
    pitch: float = 0.0
    effect: str = "none"


class SynthesizeResponse(BaseModel):
    audio: str  # base64
    audio_format: str = "mp3"
    visemes: list = []
    emotion: str = "neutral"
    duration_ms: float = 0.0
    cache_hit: bool = False
    latency_ms: float = 0.0
    rate: float = 1.0
    pitch: float = 0.0
    effect: str = "none"


@app.on_event("startup")
async def startup():
    """Initialize services, making Redis optional."""
    try:
        await redis.connect("speech")

        async def handle_rpc(msg):
            if msg.payload.get("method") == "synthesize":
                params = msg.payload.get("params", {})
                result = await tts.synthesize(
                    text=params.get("text", ""),
                    emotion=params.get("emotion", "neutral"),
                    return_visemes=params.get("return_visemes", True),
                )
                response_channel = msg.payload.get("_response_channel")
                if response_channel:
                    await redis.publish(response_channel, {
                        "status": "ok",
                        "data": result,
                    })
            elif msg.payload.get("method") == "get_voices":
                response_channel = msg.payload.get("_response_channel")
                if response_channel:
                    await redis.publish(response_channel, {
                        "status": "ok",
                        "data": {"voices": [{
                            "id": settings.tts_voice_id,
                            "name": "JARVIS",
                            "engine": settings.tts_engine,
                        }]},
                    })

        redis.subscribe("rpc:speech", handle_rpc)
        await redis.start_listening()
        logger.info("Redis connected for Speech service")
    except Exception as e:
        logger.warning(f"Redis unavailable for Speech service: {e}. TTS endpoints will work without Pub/Sub.")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "speech",
        "engine": settings.tts_engine,
        "cache_size": len(tts._cache),
    }


@app.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize(request: SynthesizeRequest):
    _metrics["total_synthesize_calls"] += 1
    _metrics["total_characters"] += len(request.text)
    _metrics["emotions_used"][request.emotion] = _metrics["emotions_used"].get(request.emotion, 0) + 1
    if request.effect and request.effect != "none":
        _metrics["effects_used"][request.effect] = _metrics["effects_used"].get(request.effect, 0) + 1

    result = await tts.synthesize(
        text=request.text,
        emotion=request.emotion,
        return_visemes=request.return_visemes,
        rate=request.rate,
        pitch=request.pitch,
        effect=request.effect,
    )

    if "error" in result:
        _metrics["errors"] += 1
        raise HTTPException(status_code=500, detail=result["error"])

    if result.get("cache_hit"):
        _metrics["cache_hits"] += 1
    else:
        _metrics["cache_misses"] += 1

    engine = "elevenlabs" if result.get("audio") else "unknown"
    _metrics["engines_used"][engine] = _metrics["engines_used"].get(engine, 0) + 1

    duration = result.get("duration_ms", 0)
    latency = result.get("latency_ms", 0)
    n = _metrics["total_synthesize_calls"]
    _metrics["avg_duration_ms"] = (_metrics["avg_duration_ms"] * (n - 1) + duration) / n
    _metrics["avg_latency_ms"] = (_metrics["avg_latency_ms"] * (n - 1) + latency) / n

    return SynthesizeResponse(
        audio=result.get("audio", ""),
        audio_format=result.get("audio_format", "mp3"),
        visemes=result.get("visemes", []),
        emotion=result.get("emotion", "neutral"),
        duration_ms=duration,
        cache_hit=result.get("cache_hit", False),
        latency_ms=latency,
        rate=result.get("rate", 1.0),
        pitch=result.get("pitch", 0.0),
        effect=result.get("effect", "none"),
    )


@app.get("/voices")
async def get_voices():
    return {
        "voices": [
            {"id": settings.tts_voice_id, "name": "JARVIS", "engine": settings.tts_engine},
        ]
    }


@app.post("/interrupt")
async def interrupt():
    tts.interrupt()
    return {"status": "interrupted"}


@app.get("/metrics")
async def get_metrics():
    uptime = time.time() - _metrics["start_time"]
    return {
        "uptime_seconds": uptime,
        "total_synthesize_calls": _metrics["total_synthesize_calls"],
        "total_characters": _metrics["total_characters"],
        "cache_hits": _metrics["cache_hits"],
        "cache_misses": _metrics["cache_misses"],
        "cache_hit_rate": round(
            _metrics["cache_hits"] / max(_metrics["total_synthesize_calls"], 1), 2
        ),
        "errors": _metrics["errors"],
        "engines_used": _metrics["engines_used"],
        "emotions_used": _metrics["emotions_used"],
        "effects_used": _metrics["effects_used"],
        "avg_duration_ms": round(_metrics["avg_duration_ms"], 2),
        "avg_latency_ms": round(_metrics["avg_latency_ms"], 2),
    }


@app.post("/cache/clear")
async def clear_cache():
    tts.clear_cache()
    return {"status": "cache_cleared"}


@app.websocket("/talk")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("Speech WebSocket connected")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            msg_type = msg.get("type", "synthesize")

            if msg_type == "synthesize":
                result = await tts.synthesize(
                    text=msg.get("text", ""),
                    emotion=msg.get("emotion", "neutral"),
                    return_visemes=msg.get("return_visemes", True),
                )

                if "error" in result:
                    await websocket.send_json({"type": "error", "payload": result})
                    continue

                await websocket.send_json({
                    "type": "audio",
                    "payload": {
                        "audio": result["audio"],
                        "format": result.get("audio_format", "mp3"),
                        "emotion": result.get("emotion", "neutral"),
                        "duration_ms": result.get("duration_ms", 0),
                    },
                })

                if result.get("visemes"):
                    await websocket.send_json({
                        "type": "visemes",
                        "payload": {"frames": result["visemes"]},
                    })

            elif msg_type == "stream":
                text = msg.get("text", "")
                chunk_size = 100
                for i in range(0, len(text), chunk_size):
                    chunk = text[i:i + chunk_size]
                    result = await tts.synthesize(chunk, msg.get("emotion", "neutral"))
                    if "audio" in result:
                        await websocket.send_json({
                            "type": "audio_chunk",
                            "payload": {
                                "audio": result["audio"],
                                "index": i // chunk_size,
                                "is_last": i + chunk_size >= len(text),
                            },
                        })

            elif msg_type == "interrupt":
                tts.interrupt()
                await websocket.send_json({
                    "type": "interrupted",
                    "payload": {"status": "ok"},
                })

    except WebSocketDisconnect:
        logger.info("Speech WebSocket disconnected")
    except Exception as e:
        logger.error(f"Speech WebSocket error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level))
    uvicorn.run("backend.speech.service:app", host="0.0.0.0", port=settings.speech_port)
