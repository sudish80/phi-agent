"""Minimal FastAPI server for PHI Agent UI testing."""

import sys, json, time, traceback
from pathlib import Path
from typing import Optional, Dict, Any
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.orchestrator.agent import agent

app = FastAPI(title="PHI Agent")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatInput(BaseModel):
    message: str
    session_id: str = "default"
    emotion: str = "neutral"
    image: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    return {
        "status": "ok",
        "total_tools": len(agent.tools),
        "llm_provider": "nvidia",
        "memory_backend": "none",
        "active_sessions": 0,
    }


@app.post("/chat")
async def chat(req: ChatInput):
    start = time.time()
    try:
        result = await agent.process(req.message, req.session_id, req.image, req.emotion)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")
    elapsed = (time.time() - start) * 1000
    return {
        "reply": result.get("reply", ""),
        "session_id": req.session_id,
        "emotion": result.get("emotion", "neutral"),
        "actions_taken": result.get("actions_taken", []),
        "memory_updated": result.get("memory_updated", False),
        "confidence": result.get("confidence", 0.7),
        "intent": result.get("intent", "general"),
        "tool_recommendations": result.get("tool_recommendations", []),
        "processing_time_ms": elapsed,
    }
