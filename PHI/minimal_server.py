"""Minimal FastAPI server for PHI Agent UI testing."""

import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from backend.orchestrator.agent import agent

app = FastAPI(title="PHI Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatInput(BaseModel):
    message: str
    session_id: str = "default"
    emotion: str = "neutral"
    image: Optional[str] = None

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
    result = await agent.process(req.message, req.session_id, req.image, req.emotion)
    elapsed = (time.time() - start) * 1000
    return {
        "reply": result.get("reply", ""),
        "session_id": req.session_id,
        "emotion": result.get("emotion", "neutral"),
        "actions_taken": result.get("actions_taken", []),
        "processing_time_ms": elapsed,
    }
