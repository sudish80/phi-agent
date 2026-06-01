"""Memory Palace Service — PHI long-term memory.

Architecture:
  - Episodic Memory: timestamped conversation logs, events
  - Semantic Memory: facts, knowledge, user preferences
  - Procedural Memory: how to perform actions, tool usage patterns
  - Spatial Memory: locations, room layouts, object positions
  - Memory Palace: metaphorical rooms that organize memories by topic,
    time period, or emotional valence. Each room has a vector embedding
    and contains related memory traces.

Uses ChromaDB for vector storage and Redis for fast cache/lookup.
"""

import os
import json
import uuid
import hashlib
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque

import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.shared.config import settings
from backend.shared.redis_client import RedisPubSub

logger = logging.getLogger(__name__)

app = FastAPI(title="PHI Memory Palace Service", version="1.0.0")

# ============================================================
# Data Models
# ============================================================

class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    SPATIAL = "spatial"


class MemoryImportance(str, Enum):
    TRIVIAL = "trivial"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryTrace:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_type: MemoryType = MemoryType.EPISODIC
    importance: MemoryImportance = MemoryImportance.NORMAL
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    room_id: Optional[str] = None
    access_count: int = 0
    last_accessed: Optional[float] = None
    decay_factor: float = 1.0
    associations: List[str] = field(default_factory=list)


@dataclass
class MemoryPalaceRoom:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    topic: str = ""
    emotional_valence: float = 0.0
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    memory_ids: List[str] = field(default_factory=list)
    adjacent_rooms: List[str] = field(default_factory=list)
    color_scheme: str = "#1a1a2e"


# Endpoints
class StoreRequest(BaseModel):
    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    importance: MemoryImportance = MemoryImportance.NORMAL
    metadata: Dict[str, Any] = {}
    room_name: Optional[str] = None


class QueryRequest(BaseModel):
    query: str
    n_results: int = 5
    memory_type: Optional[str] = None
    room_name: Optional[str] = None
    min_importance: Optional[str] = None


class MemoryResponse(BaseModel):
    id: str
    content: str
    memory_type: str
    importance: str
    timestamp: float
    metadata: Dict[str, Any]
    room_name: Optional[str] = None
    score: Optional[float] = None


# ============================================================
# ChromaDB Memory Store
# ============================================================

class ChromaStore:
    """Vector database store using ChromaDB."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._ready = False

    async def initialize(self):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        try:
            self._client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )
            self._ready = True
            logger.info(f"ChromaDB connected: {settings.chroma_url}")
        except Exception as e:
            logger.warning(f"ChromaDB unavailable, using in-memory fallback: {e}")
            self._client = chromadb.Client(
                settings=ChromaSettings(
                    is_persistent=True,
                    persist_directory="./chroma_fallback",
                    anonymized_telemetry=False,
                )
            )
            self._collection = self._client.get_or_create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )
            self._ready = True

    def _embed(self, text: str) -> List[float]:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            return model.encode(text).tolist()
        except ImportError:
            return [0.0] * settings.memory_dimension

    async def store(self, trace: MemoryTrace) -> str:
        trace.embedding = self._embed(trace.content)
        metadata = {
            "memory_type": trace.memory_type.value,
            "importance": trace.importance.value,
            "timestamp": trace.timestamp,
            "room_id": trace.room_id or "",
            "content": trace.content[:500],
        }
        metadata.update(trace.metadata)
        self._collection.add(
            ids=[trace.id],
            embeddings=[trace.embedding],
            metadatas=[metadata],
            documents=[trace.content],
        )
        return trace.id

    async def query(self, query_text: str, n_results: int = 5,
                    filter_dict: Optional[Dict] = None) -> List[Tuple[MemoryTrace, float]]:
        query_embedding = self._embed(query_text)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict,
        )
        traces = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                trace = MemoryTrace(
                    id=doc_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    memory_type=MemoryType(meta.get("memory_type", "episodic")),
                    importance=MemoryImportance(meta.get("importance", "normal")),
                    timestamp=meta.get("timestamp", 0),
                    metadata={k: v for k, v in meta.items()
                              if k not in ("memory_type", "importance", "timestamp", "room_id")},
                    room_id=meta.get("room_id"),
                )
                score = results["distances"][0][i] if results.get("distances") else 0
                traces.append((trace, 1.0 - score))
        return traces

    async def delete_old(self, max_age_days: int = 90) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
        try:
            self._collection.delete(where={"timestamp": {"$lt": cutoff}})
            return 0
        except Exception as e:
            logger.error(f"Error deleting old memories: {e}")
            return 0


# ============================================================
# Memory Palace
# ============================================================

class MemoryPalace:
    """Metaphorical memory palace organizing memories into themed rooms.

    Each room represents a topic cluster with its own embedding.
    Memories are placed in rooms based on semantic similarity.
    Adjacent rooms create associative pathways for memory traversal.
    """

    def __init__(self):
        self.rooms: Dict[str, MemoryPalaceRoom] = {}
        self._room_embeddings: Dict[str, List[float]] = {}
        self._default_rooms = [
            ("Personal", "Personal life, family, friends, relationships", "personal", 0.5),
            ("Work", "Professional life, career, projects, meetings", "work", 0.3),
            ("Technology", "Computers, programming, gadgets, AI", "technology", 0.6),
            ("Health", "Fitness, diet, medical records, wellness", "health", 0.4),
            ("Entertainment", "Movies, music, games, hobbies", "entertainment", 0.7),
            ("Education", "Learning, books, courses, knowledge", "education", 0.5),
            ("Home", "Living space, chores, maintenance, items", "home", 0.3),
            ("Finance", "Budget, expenses, investments, bills", "finance", -0.2),
            ("Travel", "Trips, destinations, plans, memories", "travel", 0.8),
            ("Social", "Events, gatherings, conversations", "social", 0.6),
            ("Projects", "Active projects, goals, todo items", "projects", 0.4),
            ("Archive", "Old memories, historical data", "archive", 0.0),
            ("Visual", "Images, scenes, visual memories", "visual", 0.5),
            ("Audio", "Sounds, music, conversations", "audio", 0.3),
            ("Emotions", "Emotional states, feelings, moods", "emotions", 0.0),
            ("Decisions", "Important decisions, reasoning", "decisions", 0.2),
            ("People", "Information about known people", "people", 0.6),
            ("Places", "Locations, addresses, routes", "places", 0.4),
            ("Calendar", "Events, schedules, appointments", "calendar", 0.3),
            ("Procedures", "How-to guides, recipes, instructions", "procedures", 0.3),
        ]

    def initialize(self):
        for name, desc, topic, valence in self._default_rooms:
            room = MemoryPalaceRoom(
                name=name,
                description=desc,
                topic=topic,
                emotional_valence=valence,
            )
            self.rooms[room.id] = room
        self._link_adjacent_rooms()
        logger.info(f"Memory Palace initialized with {len(self.rooms)} rooms")

    def _link_adjacent_rooms(self):
        room_list = list(self.rooms.values())
        for i, room in enumerate(room_list):
            if i > 0:
                room.adjacent_rooms.append(room_list[i - 1].id)
            if i < len(room_list) - 1:
                room.adjacent_rooms.append(room_list[i + 1].id)

    def assign_room(self, trace: MemoryTrace) -> Optional[str]:
        if not settings.memory_palace_enabled or not trace.embedding:
            return None

        best_room = None
        best_score = -1.0

        for room_id, room in self.rooms.items():
            from numpy import dot
            from numpy.linalg import norm
            if room.embedding and trace.embedding:
                score = dot(room.embedding, trace.embedding) / (
                    norm(room.embedding) * norm(trace.embedding) + 1e-8
                )
                if score > best_score:
                    best_score = score
                    best_room = room_id

        if best_room and best_score > 0.3:
            self.rooms[best_room].memory_ids.append(trace.id)
            return best_room
        return None

    def get_room_by_name(self, name: str) -> Optional[MemoryPalaceRoom]:
        for room in self.rooms.values():
            if room.name.lower() == name.lower():
                return room
        return None

    def get_memory_path(self, from_topic: str, to_topic: str) -> List[MemoryPalaceRoom]:
        from_room = next((r for r in self.rooms.values()
                          if r.topic == from_topic.lower()), None)
        to_room = next((r for r in self.rooms.values()
                        if r.topic == to_topic.lower()), None)
        if not from_room or not to_room or from_room.id == to_room.id:
            return []

        visited = set()
        queue = deque([(from_room.id, [from_room])])
        while queue:
            current_id, path = queue.popleft()
            if current_id == to_room.id:
                return path
            if current_id in visited:
                continue
            visited.add(current_id)
            current_room = self.rooms.get(current_id)
            if not current_room:
                continue
            for adj_id in current_room.adjacent_rooms:
                if adj_id not in visited:
                    adj_room = self.rooms.get(adj_id)
                    if adj_room:
                        queue.append((adj_id, path + [adj_room]))
        return []

    def palace_map(self) -> Dict:
        return {
            room_id: {
                "name": room.name,
                "description": room.description,
                "topic": room.topic,
                "emotional_valence": room.emotional_valence,
                "memory_count": len(room.memory_ids),
                "adjacent_rooms": [self.rooms.get(adj_id).name
                                   for adj_id in room.adjacent_rooms
                                   if adj_id in self.rooms],
            }
            for room_id, room in self.rooms.items()
        }


# ============================================================
# Memory Service
# ============================================================

class MemoryService:
    """Main memory service coordinating ChromaDB, Memory Palace, and Redis cache."""

    def __init__(self):
        self.chroma = ChromaStore()
        self.palace = MemoryPalace()
        self.redis: Optional[RedisPubSub] = None
        self._conversation_buffer: deque = deque(maxlen=50)
        self._recent_facts: Dict[str, float] = {}
        self._cache: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        await self.chroma.initialize()
        self.palace.initialize()

        self.redis = RedisPubSub()
        await self.redis.connect("memory")

        self._initialized = True
        logger.info("Memory Service initialized")

    async def store_memory(self, content: str, memory_type: MemoryType = MemoryType.EPISODIC,
                           importance: MemoryImportance = MemoryImportance.NORMAL,
                           metadata: Dict = None, room_name: str = None) -> str:
        trace = MemoryTrace(
            content=content,
            memory_type=memory_type,
            importance=importance,
            metadata=metadata or {},
        )

        if memory_type == MemoryType.EPISODIC:
            self._conversation_buffer.append(trace)
        elif memory_type == MemoryType.SEMANTIC:
            fact_key = hashlib.md5(content.encode()).hexdigest()
            self._recent_facts[fact_key] = trace.timestamp

        trace.embedding = self.chroma._embed(content)

        if room_name:
            room = self.palace.get_room_by_name(room_name)
            if room:
                trace.room_id = room.id
                room.memory_ids.append(trace.id)
        else:
            room_id = self.palace.assign_room(trace)
            trace.room_id = room_id

        trace_id = await self.chroma.store(trace)

        if self.redis:
            await self.redis.publish("memory:stored", {
                "id": trace_id,
                "type": memory_type.value,
                "importance": importance.value,
                "content_preview": content[:100],
                "room": room_name or (
                    self.palace.rooms.get(trace.room_id).name
                    if trace.room_id and trace.room_id in self.palace.rooms
                    else None
                ),
            })

        return trace_id

    async def query(self, query: str, n_results: int = 5,
                    memory_type: str = None, room_name: str = None,
                    min_importance: str = None) -> List[Dict]:
        filter_dict = {}
        if memory_type and memory_type != "all":
            filter_dict["memory_type"] = memory_type
        if min_importance:
            importance_levels = ["trivial", "low", "normal", "high", "critical"]
            min_idx = importance_levels.index(min_importance) if min_importance in importance_levels else 0
            filter_dict["importance"] = {"$in": importance_levels[min_idx:]}

        results = await self.chroma.query(query, n_results, filter_dict)
        output = []
        for trace, score in results:
            room_name = None
            if trace.room_id and trace.room_id in self.palace.rooms:
                room_name = self.palace.rooms[trace.room_id].name

            trace.access_count += 1
            trace.last_accessed = datetime.now(timezone.utc).timestamp()

            output.append({
                "id": trace.id,
                "content": trace.content,
                "memory_type": trace.memory_type.value if hasattr(trace.memory_type, 'value') else "episodic",
                "importance": trace.importance.value if hasattr(trace.importance, 'value') else "normal",
                "timestamp": trace.timestamp,
                "metadata": trace.metadata,
                "room_name": room_name,
                "score": score,
            })

        if room_name:
            room = self.palace.get_room_by_name(room_name)
            if room:
                adjacent = []
                for adj_id in room.adjacent_rooms:
                    if adj_id in self.palace.rooms:
                        adj_room = self.palace.rooms[adj_id]
                        adj_results = await self.chroma.query(
                            query, 2, {"room_id": adj_id}
                        )
                        for adj_trace, adj_score in adj_results:
                            adjacent.append({
                                "content": adj_trace.content,
                                "room": adj_room.name,
                                "score": adj_score,
                            })
                if adjacent:
                    output.append({"adjacent_memories": adjacent})

        return output

    async def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        return [
            {
                "id": c.id,
                "content": c.content[:200],
                "memory_type": c.memory_type.value if hasattr(c.memory_type, 'value') else "episodic",
                "importance": c.importance.value if hasattr(c.importance, 'value') else "normal",
            }
            for c in list(self._conversation_buffer)[-limit:]
        ]

    async def summarize_memories(self, session_id: str = None, max_items: int = 50) -> str:
        """Summarize recent memories into a condensed form."""
        query_text = ""
        n_results = max_items
        filter_dict = {"memory_type": "episodic"}
        if session_id:
            filter_dict["session_id"] = session_id

        results = await self.chroma.query(query_text, n_results, filter_dict)
        if not results:
            return "No memories to summarize."

        conversation_text = ""
        for trace, _ in results[:max_items]:
            conversation_text += trace.content + "\n"

        if len(conversation_text) > 10000:
            conversation_text = conversation_text[:10000] + "... [truncated]"

        summary_parts = []
        lines = conversation_text.split("\n")
        user_lines = [l for l in lines if l.startswith("User:")]
        phi_lines = [l for l in lines if l.startswith("PHI:")]

        if user_lines:
            summary_parts.append(f"Topics discussed: {len(user_lines)} user messages")
        if phi_lines:
            summary_parts.append(f"Responses given: {len(phi_lines)} assistant replies")

        key_phrases = self._extract_key_phrases(conversation_text)
        if key_phrases:
            summary_parts.append(f"Key topics: {', '.join(key_phrases[:5])}")

        return ". ".join(summary_parts) if summary_parts else "Memories available but summary not generated."

    def _extract_key_phrases(self, text: str, max_phrases: int = 5) -> List[str]:
        """Extract key noun phrases from text without external NLP libs."""
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "being", "have", "has", "had", "do", "does", "did", "will",
                      "would", "could", "should", "may", "might", "shall", "can",
                      "to", "of", "in", "for", "on", "with", "at", "by", "from",
                      "this", "that", "these", "those", "it", "its", "i", "you",
                      "he", "she", "we", "they", "me", "him", "her", "us", "them",
                      "my", "your", "his", "its", "our", "their", "about", "into",
                      "through", "during", "before", "after", "above", "below"}
        words = text.lower().split()
        bigrams = {}
        for i in range(len(words) - 1):
            if words[i] not in stop_words and words[i+1] not in stop_words:
                bigram = f"{words[i]} {words[i+1]}"
                bigrams[bigram] = bigrams.get(bigram, 0) + 1
        sorted_bigrams = sorted(bigrams.items(), key=lambda x: x[1], reverse=True)
        return [bg for bg, _ in sorted_bigrams[:max_phrases]]

    async def consolidate_memories(self) -> Dict:
        stats = {"consolidated": 0, "archived": 0, "promoted": 0}

        all_traces = await self.chroma.query("", n_results=1000)
        for trace, _ in all_traces:
            age_days = (datetime.now(timezone.utc).timestamp() - trace.timestamp) / 86400

            if age_days > 30 and trace.importance == MemoryImportance.TRIVIAL:
                trace.metadata["archived"] = True
                stats["archived"] += 1

        stats["total_rooms"] = len(self.palace.rooms)
        stats["total_memories"] = len(all_traces)
        return stats


memory_service = MemoryService()


# ============================================================
# FastAPI Routes
# ============================================================

@app.on_event("startup")
async def startup():
    await memory_service.initialize()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "memory",
        "initialized": memory_service._initialized,
        "rooms": len(memory_service.palace.rooms),
        "memory_count": len(memory_service._conversation_buffer),
    }


@app.post("/store", response_model=Dict)
async def store(request: StoreRequest):
    try:
        trace_id = await memory_service.store_memory(
            content=request.content,
            memory_type=request.memory_type,
            importance=request.importance,
            metadata=request.metadata,
            room_name=request.room_name,
        )
        return {"status": "ok", "id": trace_id}
    except Exception as e:
        logger.exception("Store failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/store/episodic", response_model=Dict)
async def store_episodic(request: StoreRequest):
    request.memory_type = MemoryType.EPISODIC
    return await store(request)


@app.post("/store/semantic", response_model=Dict)
async def store_semantic(request: StoreRequest):
    request.memory_type = MemoryType.SEMANTIC
    return await store(request)


@app.post("/query", response_model=List[MemoryResponse])
async def query(request: QueryRequest):
    try:
        results = await memory_service.query(
            query=request.query,
            n_results=request.n_results,
            memory_type=request.memory_type,
            room_name=request.room_name,
            min_importance=request.min_importance,
        )
        return [MemoryResponse(**r) for r in results if "adjacent_memories" not in r]
    except Exception as e:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recent")
async def recent(limit: int = 10):
    return await memory_service.get_recent_conversations(limit)


@app.get("/palace")
async def get_palace():
    return memory_service.palace.palace_map()


@app.post("/consolidate")
async def consolidate():
    return await memory_service.consolidate_memories()


@app.get("/room/{room_name}")
async def get_room(room_name: str):
    room = memory_service.palace.get_room_by_name(room_name)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{room_name}' not found")
    return {
        "id": room.id,
        "name": room.name,
        "description": room.description,
        "topic": room.topic,
        "emotional_valence": room.emotional_valence,
        "memory_count": len(room.memory_ids),
        "adjacent_rooms": [
            memory_service.palace.rooms[adj_id].name
            for adj_id in room.adjacent_rooms
            if adj_id in memory_service.palace.rooms
        ],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "store":
                trace_id = await memory_service.store_memory(
                    content=data.get("content", ""),
                    memory_type=MemoryType(data.get("type", "episodic")),
                    importance=MemoryImportance(data.get("importance", "normal")),
                    metadata=data.get("metadata", {}),
                )
                await websocket.send_json({"status": "ok", "id": trace_id})

            elif action == "query":
                results = await memory_service.query(
                    query=data.get("query", ""),
                    n_results=data.get("n", 5),
                    memory_type=data.get("memory_type"),
                )
                await websocket.send_json({"results": results})

            elif action == "palace":
                await websocket.send_json(memory_service.palace.palace_map())

    except WebSocketDisconnect:
        logger.info("Memory WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
