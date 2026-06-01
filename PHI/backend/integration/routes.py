"""Subsystem Integration — wires all new subsystems into the FastAPI app.

Adds routes for: gateway protocol, channels, MCP runtime, security, monitoring,
plugin SDK tools, automation, media, companion profiles, and model catalog.
"""

import logging
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.gateway.protocol import GatewayOp, GatewayPayload
from backend.gateway.server import gateway_server
from backend.gateway.session_store import session_store
from backend.channels.base import channel_registry, ChannelMessage, ChannelEvent
from backend.channels.webchat import webchat
from backend.channels.email_channel import EmailChannel
from backend.mcp.runtime import mcp_runtime, MCPServerConfig
from backend.mcp.channel_chain import channel_chain, ChannelChainLink
from backend.plugin_sdk.base import plugin_registry
from backend.plugin_sdk.tool_registry import get_tool_registry
from backend.security.session_security import SecurityManager, RateLimiter
security_manager = SecurityManager()
from backend.security.audit import AuditStore, log_action
audit_store = AuditStore()
from backend.monitoring.metrics import MetricsManager
metrics_manager = MetricsManager()
from backend.monitoring.logging import setup_logging, get_logger
from backend.companion.profiles import ProfileRegistry
profile_registry = ProfileRegistry()
from backend.companion.memory_manager import MemoryManager
memory_manager = MemoryManager()
from backend.automation.tasks import task_queue
from backend.automation.schedule import ScheduleManager
schedule_manager = ScheduleManager()
from backend.automation.webhook_receiver import webhook_receiver
from backend.model_catalog.catalog import (
    get_model, get_default_model, list_models_by_provider, list_all_models,
)
from backend.media.image_gen import ImageGenRegistry
image_gen_registry = ImageGenRegistry()
from backend.media.audio import AudioRegistry
audio_registry = AudioRegistry()

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Gateway Endpoints
# ============================================================

@router.get("/api/gateway/config")
async def gateway_config():
    gw = gateway_server.config
    return {
        "host": gw.host,
        "port": gw.port,
        "heartbeat_interval": gw.heartbeat_interval,
        "max_payload_size": gw.max_payload_size,
    }


@router.get("/api/gateway/stats")
async def gateway_stats():
    return {
        "clients": len(gateway_server._clients),
        "running": gateway_server._running,
    }


# ============================================================
# Session Store Endpoints
# ============================================================

@router.get("/api/sessions")
async def list_sessions(limit: int = 20):
    records = session_store.list_sessions(limit=limit)
    return {
        "sessions": [
            {
                "session_id": r.session_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "message_count": r.message_count,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str, limit: int = 50):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = session_store.get_messages(session_id, limit=limit)
    return {
        "session": {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": session.message_count,
        },
        "messages": messages,
    }


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    session_store.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ============================================================
# Channel Endpoints
# ============================================================

@router.get("/api/channels")
async def list_channels():
    channels = channel_registry.list_channels()
    return {
        "channels": [
            {
                "name": ch.name,
                "enabled": ch.config.enabled,
                "dm_policy": ch.config.dm_policy,
                "command_prefix": ch.config.command_prefix,
            }
            for ch in channels
        ],
        "total": len(channels),
    }


@router.post("/api/channels/{name}/enable")
async def enable_channel(name: str):
    ch = channel_registry.get(name)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    ch.config.enabled = True
    await ch.start()
    return {"status": "enabled", "channel": name}


@router.post("/api/channels/{name}/disable")
async def disable_channel(name: str):
    ch = channel_registry.get(name)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    ch.config.enabled = False
    await ch.stop()
    return {"status": "disabled", "channel": name}


# ============================================================
# Model Catalog Endpoints
# ============================================================

@router.get("/api/models")
async def list_models(provider: str = ""):
    if provider:
        models = list_models_by_provider(provider)
    else:
        models = list_all_models()
    return {
        "models": [
            {
                "id": m.id,
                "provider": m.provider,
                "name": m.name,
                "max_context": m.capability.max_context,
                "tool_calling": m.capability.tool_calling,
                "vision": m.capability.vision,
                "is_default": m.is_default,
            }
            for m in models
        ],
        "total": len(models),
    }


@router.get("/api/models/{model_id}")
async def get_model_detail(model_id: str):
    m = get_model(model_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return {
        "id": m.id,
        "provider": m.provider,
        "name": m.name,
        "capability": {
            "tool_calling": m.capability.tool_calling,
            "streaming": m.capability.streaming,
            "vision": m.capability.vision,
            "audio": m.capability.audio,
            "max_context": m.capability.max_context,
            "max_output": m.capability.max_output,
        },
        "cost_per_1k_input": m.cost_per_1k_input,
        "cost_per_1k_output": m.cost_per_1k_output,
        "is_default": m.is_default,
    }


# ============================================================
# Security Endpoints
# ============================================================

@router.get("/api/security/ratelimit")
async def get_rate_limits():
    return {"rate_limits": "active"}


@router.get("/api/security/audit")
async def get_audit_log(limit: int = 50):
    entries = audit_store.get_entries(limit=limit)
    return {
        "entries": [
            {
                "timestamp": e.timestamp,
                "session_id": e.session_id,
                "action": e.action,
                "success": e.success,
            }
            for e in entries
        ],
        "total": len(entries),
    }


# ============================================================
# Monitoring Endpoints
# ============================================================

@router.get("/api/metrics")
async def get_metrics():
    return metrics_manager.render_json()


@router.get("/api/metrics/prometheus")
async def get_prometheus_metrics():
    return metrics_manager.render_prometheus()


# ============================================================
# Plugin SDK Endpoints
# ============================================================

@router.get("/api/plugins/sdk")
async def list_sdk_plugins():
    plugins = plugin_registry.list_plugins()
    return {
        "plugins": [
            {
                "name": p.manifest.name,
                "version": p.manifest.version,
                "description": p.manifest.description,
                "tools": p.manifest.tools,
            }
            for p in plugins
        ],
        "total": len(plugins),
    }


@router.get("/api/tools/registry")
async def list_registered_tools():
    tools = get_tool_registry().list_tools()
    return {
        "tools": [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in tools
        ],
        "total": len(tools),
    }


# ============================================================
# MCP Endpoints
# ============================================================

@router.get("/api/mcp/servers")
async def list_mcp_servers():
    return {"servers": list(mcp_runtime._servers.keys())}


@router.post("/api/mcp/servers")
async def register_mcp_server(name: str, command: str, args: List[str] = [],
                                transport: str = "stdio"):
    config = MCPServerConfig(command=command, args=args, transport=transport)
    mcp_runtime.register_server(name, config)
    return {"status": "registered", "name": name}


@router.post("/api/mcp/discover")
async def discover_mcp_tools():
    tools = await mcp_runtime.discover_tools()
    return {
        "tools": [{"name": t.name, "description": t.description} for t in tools],
        "total": len(tools),
    }


# ============================================================
# Automation Endpoints
# ============================================================

@router.get("/api/tasks")
async def list_tasks(limit: int = 20):
    tasks = task_queue.list_tasks(limit=limit)
    return {
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "workflow": t.workflow,
                "status": t.status.value,
                "created_at": t.created_at,
                "error": t.error,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": task.id,
        "name": task.name,
        "workflow": task.workflow,
        "status": task.status.value,
        "params": task.params,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
    }


@router.get("/api/schedules")
async def list_schedules():
    entries = schedule_manager.list_schedules()
    return {
        "schedules": [
            {
                "id": e.id,
                "action": e.action,
                "time": e.time,
                "day_of_week": e.day_of_week,
                "active": e.active,
            }
            for e in entries
        ],
        "total": len(entries),
    }


@router.get("/api/webhooks/routes")
async def list_webhooks():
    return {"routes": list(webhook_receiver._routes.keys())}


# ============================================================
# Companion Endpoints
# ============================================================

@router.get("/api/companion/profiles")
async def list_profiles():
    profiles = profile_registry.list_profiles()
    return {
        "profiles": [
            {
                "name": p.name,
                "voice_tone": p.voice_tone,
                "response_style": p.response_style,
            }
            for p in profiles
        ],
        "total": len(profiles),
    }


@router.get("/api/companion/memory/{user_id}")
async def get_companion_memory(user_id: str):
    memory = memory_manager.get_memory(user_id)
    if not memory:
        return {"user_id": user_id, "facts": [], "preferences": {}}
    return {
        "user_id": user_id,
        "facts": memory.facts,
        "preferences": memory.preferences,
        "summaries": memory.interaction_summaries,
    }


# ============================================================
# Media Endpoints
# ============================================================

@router.get("/api/media/image/generators")
async def list_image_generators():
    gens = image_gen_registry.list_generators()
    return {"generators": list(gens.keys())}


@router.get("/api/media/audio/processors")
async def list_audio_processors():
    procs = audio_registry.list_processors()
    return {"processors": list(procs.keys())}


# ============================================================
# Webhook Receiver Endpoint
# ============================================================

@router.post("/api/webhooks/{path:path}")
async def receive_webhook(path: str, payload: Dict[str, Any],
                           request_headers: Optional[Dict[str, str]] = None):
    result = await webhook_receiver.dispatch(
        f"/{path}", payload, request_headers or {}
    )
    return {"status": "processed", "result": result}


# ============================================================
# Init — register default channels, plugins, MCP servers
# ============================================================

async def init_subsystems():
    logger.info("Initializing subsystem integrations...")

    # Register default channels
    channel_registry.register(webchat)
    email_channel = EmailChannel()
    channel_registry.register(email_channel)
    await channel_registry.start_all()

    # Start gateway server (protocol layer)
    await gateway_server.start()

    # Register default image generator
    try:
        from backend.media.image_gen import DummyImageGenerator
        image_gen_registry.register("dummy", DummyImageGenerator())
    except Exception as e:
        logger.warning("Image generator init: %s", e)

    # Register default audio processor
    try:
        from backend.media.audio import DummyAudioProcessor
        audio_registry.register("dummy", DummyAudioProcessor())
    except Exception as e:
        logger.warning("Audio processor init: %s", e)

    logger.info("Subsystem integrations initialized")
