"""Orchestrator Service — central brain of J.A.R.V.I.S.

FastAPI application with:
  - POST /chat: text-based conversation
  - WS /ws: bidirectional WebSocket for audio/video/text
  - GET /status: health check
  - Session management per user
  - Redis Pub/Sub for inter-service communication
"""

import os
import sys
import json
import uuid
import base64
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
import aiohttp
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.shared.config import settings
from backend.shared.redis_client import RedisPubSub
from backend.shared.llm_client import llm_client
from backend.orchestrator.models import (
    ChatRequest, ChatResponse, SessionCreate, SessionInfo,
    StatusResponse, WebSocketMessage,
)
from backend.orchestrator.agent import agent
from backend.audio.audio_manager import AudioManager
from backend.audio.scheduler import AudioScheduler
from backend.tools.telemetry import (
    record_tool_call, get_stats, get_history, get_live_events,
    get_slow_tools, get_error_hotspots, get_hourly_summary,
    instrument_agent, subscribe as telemetry_subscribe,
)
from backend.tools.plugin_loader import (
    scan_plugins, list_plugins, get_plugin, enable_plugin, disable_plugin,
    reload_plugin, start_watcher as plugin_start_watcher,
    stop_watcher as plugin_stop_watcher,
    create_example_plugin, register_plugin_tools,
)
from backend.tools.multi_agent import (
    spawn_agent, list_agents, get_agent_result, cancel_agent,
    multi_agent_collaborate,
)
from backend.tools.middleware import setup_logging

logger = logging.getLogger(__name__)

# ============================================================
# App setup
# ============================================================

redis = RedisPubSub()

# Session management
sessions: Dict[str, Dict] = {}
start_time = time.time()

# Audio Manager — full lifecycle: storage, dedup, compression, search, memory linking
audio_manager = AudioManager()
audio_scheduler = AudioScheduler(audio_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Orchestrator starting up...")

    async def _safe(name, coro, timeout=5):
        try:
            await asyncio.wait_for(coro, timeout=timeout)
            logger.info(f"{name} ready")
        except asyncio.TimeoutError:
            logger.warning(f"{name} timed out after {timeout}s, continuing")
        except Exception as e:
            logger.warning(f"{name} failed: {e}")

    await _safe("redis.connect", redis.connect("orchestrator"), 3)
    await _safe("redis.listen", redis.start_listening(), 2)
    app.state.memory_service = None

    await _safe("audio_manager.initialize", audio_manager.initialize(), 5)
    try:
        audio_scheduler.start()
        logger.info("AudioScheduler started")
    except Exception as e:
        logger.warning(f"AudioScheduler start failed: {e}")

    try:
        from backend.tools.plugin_loader import scan_plugins, register_plugin_tools, start_watcher
        plugin_results = await asyncio.wait_for(asyncio.to_thread(scan_plugins), timeout=3)
        if plugin_results:
            register_plugin_tools(agent.tools)
            logger.info(f"Plugin system: {len(plugin_results)} plugin(s) loaded")
        start_watcher(interval=10.0)
    except asyncio.TimeoutError:
        logger.warning("Plugin scan timed out")
    except Exception as e:
        logger.warning(f"Plugin system init: {e}")

    yield

    audio_scheduler.stop()
    await redis.disconnect()
    logger.info("Orchestrator shutting down...")


app = FastAPI(
    title="J.A.R.V.I.S. Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Internal middleware
from backend.tools.middleware import RequestTimingMiddleware, RequestIDMiddleware, LogLevelMiddleware
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LogLevelMiddleware)

# In-memory cache for endpoint management
_cache_store: Dict[str, Any] = {}
_cache_hits = 0
_cache_misses = 0

# Mount static audio directory for serving files
AUDIO_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

# WebSocket connections
ws_connections: Dict[str, List[WebSocket]] = {}


# ============================================================
# Memory service integration
# ============================================================

_memory_service = None

async def get_memory_service():
    global _memory_service
    if _memory_service is None:
        try:
            from backend.memory.service import MemoryService
            _memory_service = MemoryService()
            await _memory_service.initialize()
        except Exception as e:
            logger.warning(f"Memory service not available: {e}")
            _memory_service = None
    return _memory_service


# ============================================================
# TTS Synthesis
# ============================================================

_speech_session: Optional[aiohttp.ClientSession] = None

async def get_speech_session():
    global _speech_session
    if _speech_session is None or _speech_session.closed:
        _speech_session = aiohttp.ClientSession()
    return _speech_session

async def synthesize_speech(
    text: str,
    emotion: str = "neutral",
    session_id: str = "",
    source: str = "elevenlabs",
) -> Optional[str]:
    """Call the speech service, store via AudioManager, return URL path."""
    speech_url = f"http://127.0.0.1:{settings.speech_port}/synthesize"
    try:
        session = await get_speech_session()
        async with session.post(speech_url, json={
            "text": text,
            "emotion": emotion,
            "return_visemes": True,
            "humanize": True,
            "rate": 1.0,
            "pitch": 0.0,
            "effect": "none",
        }, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning(f"Speech service returned {resp.status}")
                return None
            data = await resp.json()
            audio_b64 = data.get("audio", "")
            if not audio_b64:
                return None
            audio_format = data.get("audio_format", "mp3")
            audio_bytes = base64.b64decode(audio_b64)

            entry = await audio_manager.store_audio(
                audio_bytes=audio_bytes,
                format=audio_format,
                category="generated/responses",
                transcript=text,
                emotion=emotion,
                source=source,
                sample_rate=24000,
                channels=1,
                duration_ms=0.0,
                linked_conversation_id=session_id,
            )
            if entry:
                return entry.audio_url
            return None
    except asyncio.TimeoutError:
        logger.warning("Speech service timeout")
    except aiohttp.ClientConnectorError:
        logger.warning("Speech service unavailable (is it running on port 8003?)")
    except Exception as e:
        logger.warning(f"Speech synthesis error: {e}")
    return None


# ============================================================
# HTTP Endpoints
# ============================================================

@app.get("/health")
async def health():
    return StatusResponse(
        status="ok",
        uptime_seconds=time.time() - start_time,
        active_sessions=len(sessions),
        memory_status="connected" if _memory_service else "disconnected",
        services={
            "redis": "connected",
        },
        token_usage=llm_client.get_usage_stats(),
    ).model_dump()


@app.get("/tools")
async def list_tools(category: str = ""):
    from backend.tools.autoregister import get_all_tool_batches
    all_tools = []
    for batch in get_all_tool_batches():
        for t in batch:
            if category and t.category != category:
                continue
            all_tools.append({
                "name": t.name,
                "description": t.description[:120],
                "category": t.category,
                "parameters": t.parameters,
            })
    return {"total": len(all_tools), "tools": all_tools}


@app.get("/tools/{name}")
async def get_tool_detail(name: str):
    from backend.tools.autoregister import get_all_tool_batches
    for batch in get_all_tool_batches():
        for t in batch:
            if t.name == name:
                return {"name": t.name, "description": t.description, "category": t.category, "parameters": t.parameters}
    raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
        return {"status": "deleted", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@app.post("/cache/clear")
async def clear_cache():
    global _cache_hits, _cache_misses
    _cache_store.clear()
    _cache_hits = 0
    _cache_misses = 0
    return {"status": "cache cleared"}


@app.get("/cache/stats")
async def cache_stats():
    return {
        "size": len(_cache_store),
        "hits": _cache_hits,
        "misses": _cache_misses,
        "keys": list(_cache_store.keys())[:50],
    }


@app.post("/logs/level")
async def set_log_level(level: str):
    from backend.tools.middleware import LogLevelMiddleware
    if LogLevelMiddleware.set_level(level):
        return {"status": "ok", "level": level.upper()}
    raise HTTPException(status_code=400, detail=f"Invalid log level: {level}. Use DEBUG, INFO, WARNING, ERROR, CRITICAL")


@app.get("/logs/level")
async def get_log_level():
    from backend.tools.middleware import LogLevelMiddleware
    return {"level": LogLevelMiddleware.get_level()}


@app.post("/shutdown")
async def shutdown():
    logger.warning("Shutdown requested via API")
    asyncio.create_task(_delayed_shutdown())
    return {"status": "shutting down"}


async def _delayed_shutdown():
    await asyncio.sleep(1)
    os._exit(0)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    process_start = time.time()

    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = {
            "created_at": datetime.now(timezone.utc),
            "last_active": datetime.now(timezone.utc),
            "message_count": 0,
            "emotion": "neutral",
            "user_name": settings.user_name,
        }

    try:
        result = await agent.process(
            message=request.message,
            session_id=session_id,
            image=request.image,
            emotion=request.emotion,
        )
    except Exception as e:
        logger.exception("Agent processing failed")
        raise HTTPException(status_code=500, detail=str(e))

    sessions[session_id]["last_active"] = datetime.now(timezone.utc)
    sessions[session_id]["message_count"] += 1
    sessions[session_id]["emotion"] = result.get("emotion", "neutral")

    processing_ms = (time.time() - process_start) * 1000

    reply = result.get("reply", "I apologize, I encountered an error.")
    emotion = result.get("emotion", "neutral")

    audio_url = await synthesize_speech(reply, emotion, session_id=session_id)

    return ChatResponse(
        reply=reply,
        session_id=session_id,
        emotion=emotion,
        audio_url=audio_url,
        actions_taken=result.get("actions_taken", []),
        memory_updated=result.get("memory_updated", False),
        processing_time_ms=processing_ms,
        confidence=result.get("confidence", 0.7),
        intent=result.get("intent", "general"),
        tool_recommendations=result.get("tool_recommendations", []),
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = {
            "created_at": datetime.now(timezone.utc),
            "last_active": datetime.now(timezone.utc),
            "message_count": 0,
            "emotion": "neutral",
            "user_name": settings.user_name,
        }

    async def event_stream():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        async for event in agent.process_stream(
            message=request.message,
            session_id=session_id,
            emotion=request.emotion,
        ):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/avatar/expression")
async def avatar_expression(emotion: str = "neutral", speaking: bool = False):
    """Get avatar facial expression blend shapes for a given emotion."""
    try:
        from backend.actions.avatar import (
            get_expression, get_head_movement, get_body_language
        )
        return {
            "expression": get_expression(emotion),
            "head": get_head_movement(speaking),
            "gestures": get_body_language(emotion),
            "emotion": emotion,
        }
    except Exception as e:
        logger.warning(f"Avatar expression unavailable: {e}")
        return {"expression": {}, "head": {}, "gestures": [], "emotion": emotion}


@app.post("/vision/scene")
async def scene_understanding(image_b64: str, query: str = "Describe this scene in detail"):
    """Analyze an image and describe the scene."""
    try:
        from backend.vision.detector import detect_objects
        result = await detect_objects(image_b64)
        return {
            "objects_detected": result.get("objects", []),
            "scene_description": result.get("description", "Scene analysis complete."),
            "confidence": result.get("confidence", 0.0),
        }
    except Exception as e:
        logger.warning(f"Scene understanding unavailable: {e}")
        return {"objects_detected": [], "scene_description": "Scene analysis unavailable.", "confidence": 0.0}


@app.post("/session", response_model=Dict)
async def create_session(create: SessionCreate):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "created_at": datetime.now(timezone.utc),
        "last_active": datetime.now(timezone.utc),
        "message_count": 0,
        "emotion": "neutral",
        "user_name": create.user_name,
        "settings": create.settings,
    }
    return {"session_id": session_id, "status": "created"}


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    s = sessions[session_id]
    return SessionInfo(
        session_id=session_id,
        user_name=s.get("user_name", settings.user_name),
        created_at=s["created_at"],
        last_active=s["last_active"],
        message_count=s["message_count"],
        emotion=s.get("emotion", "neutral"),
    ).model_dump()


@app.get("/status")
async def status():
    """Return system status including tools and categories."""
    import traceback
    try:
        tools_list = agent.tools.list_tools()
        categories = {}
        for t in tools_list:
            cat = t.get("category", "uncategorized")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(t["name"])
        return {
            "status": "ok",
            "total_tools": len(tools_list),
            "tools": tools_list,
            "categories": {k: len(v) for k, v in categories.items()},
            "active_sessions": len(sessions),
            "memory_backend": settings.memory_backend,
            "llm_provider": settings.llm_provider,
        }
    except Exception as e:
        logger.error(f"Status error: {e}\n{traceback.format_exc()}")
        return {"status": "error", "detail": str(e)}


# ============================================================
# Telemetry Endpoints
# ============================================================


@app.get("/telemetry/stats")
async def telemetry_stats(reset: bool = False):
    """Get aggregated tool usage statistics."""
    return get_stats(reset=reset)


@app.get("/telemetry/history")
async def telemetry_history(limit: int = 100, tool: str = "", session: str = ""):
    """Get historical tool call records."""
    return {"records": get_history(limit=limit, tool=tool, session=session)}


@app.get("/telemetry/live")
async def telemetry_live(count: int = 50):
    """Get recent telemetry events from ring buffer."""
    return {"events": get_live_events(count=count)}


@app.get("/telemetry/slow-tools")
async def telemetry_slow(min_calls: int = 5, threshold_ms: float = 1000):
    """Find slow tools (avg duration above threshold)."""
    return {"slow_tools": get_slow_tools(min_calls=min_calls, threshold_ms=threshold_ms)}


@app.get("/telemetry/error-hotspots")
async def telemetry_errors(min_errors: int = 3):
    """Find tools with high error rates."""
    return {"hotspots": get_error_hotspots(min_errors=min_errors)}


@app.get("/telemetry/hourly")
async def telemetry_hourly(hours: int = 24):
    """Get hourly aggregated summaries."""
    return {"hours": get_hourly_summary(hours=hours)}


# ============================================================
# Plugin Endpoints
# ============================================================


@app.get("/plugins")
async def plugin_list():
    """List all loaded plugins with status."""
    all_plugins = list_plugins()
    return {
        "plugins": [
            {
                "name": p.name, "version": p.version, "author": p.author,
                "description": p.description, "enabled": p.enabled,
                "tools_count": p.tools_count, "error": p.error,
                "loaded_at": p.loaded_at,
            }
            for p in all_plugins
        ],
        "total": len(all_plugins),
        "watcher_running": True,
    }


@app.post("/plugins/scan")
async def plugin_scan():
    """Scan the plugins directory for new plugins."""
    results = scan_plugins()
    return {
        "loaded": [{"name": p.name, "version": p.version, "tools": p.tools_count} for p in results.values()],
        "count": len(results),
    }


@app.post("/plugins/{name}/enable")
async def plugin_enable(name: str):
    """Enable a plugin."""
    ok = enable_plugin(name)
    if ok:
        # Re-register tools
        register_plugin_tools(agent.tools)
    return {"status": "ok" if ok else "not_found", "plugin": name}


@app.post("/plugins/{name}/disable")
async def plugin_disable(name: str):
    """Disable a plugin."""
    ok = disable_plugin(name)
    return {"status": "ok" if ok else "not_found", "plugin": name}


@app.post("/plugins/{name}/reload")
async def plugin_reload(name: str):
    """Reload a plugin from disk."""
    info = reload_plugin(name)
    if info:
        register_plugin_tools(agent.tools)
        return {"status": "ok", "plugin": info.name, "tools": info.tools_count}
    return {"status": "not_found", "plugin": name}


@app.post("/plugins/example")
async def plugin_create_example():
    """Create an example plugin file."""
    filepath = create_example_plugin()
    info = scan_plugins()
    register_plugin_tools(agent.tools)
    return {"status": "created", "path": filepath, "plugins_loaded": len(info)}


@app.post("/plugins/watcher/start")
async def plugin_watcher_start(interval: float = 5.0):
    """Start the plugin file watcher."""
    plugin_start_watcher(interval=interval)
    return {"status": "started", "interval": interval}


@app.post("/plugins/watcher/stop")
async def plugin_watcher_stop():
    """Stop the plugin file watcher."""
    plugin_stop_watcher()
    return {"status": "stopped"}


# ============================================================
# Multi-Agent Endpoints
# ============================================================


@app.post("/agents/spawn")
async def api_spawn_agent(role: str, task: str, context: str = "",
                           parent_session: str = "default"):
    """Spawn a sub-agent."""
    result = await spawn_agent(role, task, context, parent_session)
    return json.loads(result)


@app.get("/agents")
async def api_list_agents(status: str = "", parent_session: str = ""):
    """List sub-agents."""
    result = await list_agents(status, parent_session)
    return json.loads(result)


@app.get("/agents/{agent_id}")
async def api_get_agent(agent_id: str):
    """Get agent result."""
    result = await get_agent_result(agent_id)
    return json.loads(result)


@app.post("/agents/{agent_id}/cancel")
async def api_cancel_agent(agent_id: str):
    """Cancel a running agent."""
    result = await cancel_agent(agent_id)
    return json.loads(result)


@app.post("/agents/collaborate")
async def api_collaborate(primary_role: str, supporting_roles: str,
                          task: str, context: str = "",
                          parent_session: str = "default"):
    """Multi-agent collaboration."""
    result = await multi_agent_collaborate(
        primary_role, supporting_roles, task, context, parent_session
    )
    return json.loads(result)


# ============================================================
# Audio Management Endpoints
# ============================================================


@app.get("/audio/search")
async def audio_search(
    query: str = "",
    speaker: str = "",
    emotion: str = "",
    category: str = "",
    date_from: str = "",
    date_to: str = "",
    conversation_id: str = "",
    task_id: str = "",
    limit: int = 50,
    offset: int = 0,
):
    """Search the audio database by transcript, speaker, emotion, date, or linked entity."""
    results = await audio_manager.search(
        query=query,
        speaker=speaker,
        emotion=emotion,
        category=category,
        date_from=date_from,
        date_to=date_to,
        linked_conversation_id=conversation_id,
        linked_task_id=task_id,
        limit=limit,
        offset=offset,
    )
    return {"results": [r.__dict__ for r in results], "count": len(results)}


@app.get("/audio/stats")
async def audio_stats():
    """Return audio storage statistics."""
    return await audio_manager.get_stats()


@app.post("/audio/link/conversation")
async def link_audio_to_conversation(audio_uuid: str, conversation_id: str):
    success = await audio_manager.link_to_conversation(audio_uuid, conversation_id)
    return {"success": success}


@app.post("/audio/link/task")
async def link_audio_to_task(audio_uuid: str, task_id: str):
    success = await audio_manager.link_to_task(audio_uuid, task_id)
    return {"success": success}


@app.post("/audio/link/thought")
async def link_audio_to_thought(audio_uuid: str, thought_id: str):
    success = await audio_manager.link_to_thought(audio_uuid, thought_id)
    return {"success": success}


@app.get("/audio/entry/{audio_uuid}")
async def get_audio_entry(audio_uuid: str):
    entry = await audio_manager.get_audio(audio_uuid)
    if not entry:
        raise HTTPException(status_code=404, detail="Audio entry not found")
    return entry.to_dict()


@app.delete("/audio/entry/{audio_uuid}")
async def delete_audio_entry(audio_uuid: str):
    success = await audio_manager.delete_audio(audio_uuid)
    if not success:
        raise HTTPException(status_code=404, detail="Audio entry not found")
    return {"success": True}


# ============================================================
# WebSocket Endpoint
# ============================================================

_ws_telemetry_subs: Dict[str, List[WebSocket]] = {}


def _broadcast_telemetry(event: dict):
    """Push telemetry event to all subscribed WebSocket connections."""
    dead = []
    for sid, sockets in _ws_telemetry_subs.items():
        for ws in sockets:
            try:
                asyncio.ensure_future(ws.send_json({
                    "type": "telemetry",
                    "payload": event,
                }))
            except Exception:
                dead.append((sid, ws))
    for sid, ws in dead:
        try:
            _ws_telemetry_subs[sid].remove(ws)
        except (ValueError, KeyError):
            pass


# Register the telemetry bridge
telemetry_unsub = telemetry_subscribe(_broadcast_telemetry)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "default"):
    await websocket.accept()
    logger.info(f"WebSocket connected: {session_id}")

    if session_id not in ws_connections:
        ws_connections[session_id] = []
    ws_connections[session_id].append(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "payload": {"message": "Invalid JSON"},
                })
                continue

            msg_type = data.get("type", "chat")
            payload = data.get("payload", {})

            if msg_type == "chat":
                await websocket.send_json({
                    "type": "mode",
                    "payload": {"mode": "thinking"},
                    "session_id": session_id,
                })
                t0 = time.perf_counter()
                result = await agent.process(
                    message=payload.get("text", ""),
                    session_id=session_id,
                    image=payload.get("image"),
                    emotion=payload.get("emotion", "neutral"),
                )
                duration_ms = (time.perf_counter() - t0) * 1000
                record_tool_call("chat_process", "ai", duration_ms,
                               success=True, session_id=session_id)

                reply = result["reply"]
                emotion = result["emotion"]

                audio_url = await synthesize_speech(reply, emotion, session_id=session_id)

                response = {
                    "type": "chat",
                    "payload": {
                        "reply": reply,
                        "emotion": emotion,
                        "actions": result["actions_taken"],
                        "audio_url": audio_url,
                    },
                    "session_id": session_id,
                }
                await websocket.send_json(response)

                await websocket.send_json({
                    "type": "mode",
                    "payload": {"mode": "speaking"},
                    "session_id": session_id,
                })

                if emotion != "neutral":
                    await websocket.send_json({
                        "type": "emotion",
                        "payload": {"emotion": emotion},
                        "session_id": session_id,
                    })

            elif msg_type == "audio":
                audio_bytes = base64.b64decode(payload.get("audio", ""))
                await websocket.send_json({
                    "type": "mode",
                    "payload": {"mode": "listening"},
                    "session_id": session_id,
                })
                from backend.hearing.stt import transcribe_audio
                text = await transcribe_audio(audio_bytes)
                if text:
                    await websocket.send_json({
                        "type": "chat",
                        "payload": {"reply": result["reply"], "emotion": result["emotion"]},
                        "session_id": session_id,
                    })

            elif msg_type == "image":
                await websocket.send_json({
                    "type": "vision_ack",
                    "payload": {"status": "received"},
                    "session_id": session_id,
                })

            elif msg_type == "command":
                cmd = payload.get("command", "")
                if cmd == "reset_session":
                    agent.reset_session(session_id)
                    await websocket.send_json({
                        "type": "command_ack",
                        "payload": {"status": "session_reset"},
                        "session_id": session_id,
                    })
                elif cmd == "get_status":
                    await websocket.send_json({
                        "type": "status",
                        "payload": {
                            "sessions": len(sessions),
                            "uptime": time.time() - start_time,
                        },
                        "session_id": session_id,
                    })
                elif cmd == "subscribe_telemetry":
                    if session_id not in _ws_telemetry_subs:
                        _ws_telemetry_subs[session_id] = []
                    _ws_telemetry_subs[session_id].append(websocket)
                    await websocket.send_json({
                        "type": "command_ack",
                        "payload": {"status": "telemetry_subscribed"},
                        "session_id": session_id,
                    })
                elif cmd == "unsubscribe_telemetry":
                    if session_id in _ws_telemetry_subs:
                        _ws_telemetry_subs[session_id] = [
                            ws for ws in _ws_telemetry_subs[session_id] if ws != websocket
                        ]
                    await websocket.send_json({
                        "type": "command_ack",
                        "payload": {"status": "telemetry_unsubscribed"},
                        "session_id": session_id,
                    })

            elif msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "payload": {"timestamp": time.time()},
                    "session_id": session_id,
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if session_id in ws_connections:
            ws_connections[session_id] = [
                ws for ws in ws_connections[session_id] if ws != websocket
            ]
        if session_id in _ws_telemetry_subs:
            _ws_telemetry_subs[session_id] = [
                ws for ws in _ws_telemetry_subs[session_id] if ws != websocket
            ]


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    setup_logging(settings.log_level)
    uvicorn.run(
        "backend.orchestrator.main:app",
        host="0.0.0.0",
        port=settings.orchestrator_port,
        reload=True,
        ws_ping_interval=25,
        ws_ping_timeout=30,
    )
