"""Pydantic models for the Orchestrator API."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    emotion: str = "neutral"
    image: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    emotion: str = "neutral"
    audio_url: Optional[str] = None
    visemes: Optional[List[Dict]] = None
    actions_taken: List[str] = []
    memory_updated: bool = False
    processing_time_ms: float = 0.0
    confidence: float = 0.7
    intent: str = "general"
    tool_recommendations: List[Dict] = []


class SessionCreate(BaseModel):
    user_name: str = "User"
    settings: Dict[str, Any] = {}


class SessionInfo(BaseModel):
    session_id: str
    user_name: str
    created_at: datetime
    last_active: datetime
    message_count: int
    emotion: str = "neutral"


class StatusResponse(BaseModel):
    status: str
    service: str = "orchestrator"
    version: str = "1.0.0"
    uptime_seconds: float
    active_sessions: int
    memory_status: str
    services: Dict[str, str] = {}
    token_usage: Dict[str, int] = {}


class ToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None


class AgentThought(BaseModel):
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict] = None
    observation: Optional[str] = None
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class WebSocketMessage(BaseModel):
    type: str = Field(..., description="chat, audio, video, command, emotion, viseme")
    payload: Dict[str, Any] = {}
    session_id: str = "default"
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


class ProactiveSuggestion(BaseModel):
    suggestion: str
    confidence: float
    reason: str
    context: Dict[str, Any] = {}
