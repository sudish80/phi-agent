"""Minimal FastAPI server for PHI Agent UI testing."""

import sys, json, time, traceback, logging
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("phi.server")

agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    logger.info("Loading PHI Agent...")
    try:
        from backend.orchestrator.agent import agent as _agent
        agent = _agent
        logger.info("Agent loaded successfully")
    except Exception as e:
        logger.error("Failed to load agent: %s", e)
        logger.error(traceback.format_exc())
        agent = None
    yield
    logger.info("PHI Agent shutting down")


app = FastAPI(title="PHI Agent", lifespan=lifespan)

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
    if agent is None:
        return {"status": "degraded", "error": "agent not loaded"}
    return {
        "status": "ok",
        "total_tools": len(agent.tools),
        "llm_provider": "nvidia",
        "memory_backend": "none",
        "active_sessions": 0,
    }


@app.post("/chat")
async def chat(req: ChatInput):
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not available")
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
