import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone

from backend.calling.models import CallSession, CallState

logger = logging.getLogger(__name__)


class WebRTCSignaling:
    """WebRTC signaling server managing peer connections and rooms."""

    def __init__(self):
        self._rooms: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, CallSession] = {}
        self._peers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._timeout_task: Optional[asyncio.Task] = None
        self._timeout_sec = 300

    async def start_timeout_handler(self):
        if self._timeout_task and not self._timeout_task.done():
            return
        self._timeout_task = asyncio.create_task(self._timeout_loop())

    async def _timeout_loop(self):
        while True:
            await asyncio.sleep(30)
            await self._check_timeouts()

    async def _check_timeouts(self):
        now = time.time()
        async with self._lock:
            stale = []
            for session_id, session in self._sessions.items():
                if session.state in (CallState.connected, CallState.connecting):
                    last_active = getattr(session, "_last_active", None)
                    if last_active and (now - last_active) > self._timeout_sec:
                        stale.append(session_id)
            for sid in stale:
                session = self._sessions.get(sid)
                if session:
                    session.state = CallState.ended
                    session.end_time = datetime.now(timezone.utc).isoformat()
                    logger.info(f"Session {sid} auto-ended due to inactivity")

    async def create_room(self, room_id: str) -> Dict[str, Any]:
        async with self._lock:
            if room_id in self._rooms:
                raise ValueError(f"Room {room_id} already exists")
            room = {
                "room_id": room_id,
                "peers": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_active": time.time(),
            }
            self._rooms[room_id] = room
            self._peers[room_id] = set()
            logger.info(f"Room {room_id} created")
            return room

    async def join_room(self, room_id: str, peer_id: str) -> Dict[str, Any]:
        async with self._lock:
            if room_id not in self._rooms:
                raise ValueError(f"Room {room_id} does not exist")
            self._rooms[room_id]["peers"].append(peer_id)
            self._rooms[room_id]["last_active"] = time.time()
            self._peers[room_id].add(peer_id)
            logger.info(f"Peer {peer_id} joined room {room_id}")
            existing_peers = [p for p in self._peers[room_id] if p != peer_id]
            return {"room_id": room_id, "peer_id": peer_id, "peers": list(existing_peers)}

    async def leave_room(self, room_id: str, peer_id: str):
        async with self._lock:
            if room_id in self._rooms:
                self._rooms[room_id]["peers"] = [p for p in self._rooms[room_id]["peers"] if p != peer_id]
                self._peers[room_id].discard(peer_id)
                logger.info(f"Peer {peer_id} left room {room_id}")
                if not self._peers[room_id]:
                    del self._rooms[room_id]
                    del self._peers[room_id]
                    logger.info(f"Room {room_id} deleted (no peers)")

    async def list_rooms(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [dict(r) for r in self._rooms.values()]

    async def create_offer(self, session_id: str, sdp: str = "") -> CallSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                session = CallSession(id=session_id)
                self._sessions[session_id] = session
            session.sdp_offer = sdp
            session.state = CallState.connecting
            session.start_time = datetime.now(timezone.utc).isoformat()
            session._last_active = time.time()
            logger.info(f"Offer created for session {session_id}")
            return session

    async def handle_answer(self, session_id: str, sdp: str) -> Optional[CallSession]:
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"No session found for answer: {session_id}")
                return None
            session.sdp_answer = sdp
            session.state = CallState.connected
            session._last_active = time.time()
            logger.info(f"Answer handled for session {session_id}")
            return session

    async def add_ice_candidate(self, session_id: str, candidate: Dict[str, Any]):
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"No session for ICE candidate: {session_id}")
                return
            session.ice_candidates.append(candidate)
            session._last_active = time.time()

    async def get_session(self, session_id: str) -> Optional[CallSession]:
        async with self._lock:
            return self._sessions.get(session_id)

    async def end_session(self, session_id: str):
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.state = CallState.ended
                session.end_time = datetime.now(timezone.utc).isoformat()
                if session.start_time:
                    start = datetime.fromisoformat(session.start_time)
                    end = datetime.fromisoformat(session.end_time)
                    session.duration_sec = (end - start).total_seconds()
                logger.info(f"Session {session_id} ended (duration={session.duration_sec}s)")

    async def get_peer_count(self, room_id: str) -> int:
        async with self._lock:
            return len(self._peers.get(room_id, set()))

    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any], exclude_peer: Optional[str] = None):
        async with self._lock:
            room_peers = self._peers.get(room_id, set())
            for peer_id in room_peers:
                if peer_id == exclude_peer:
                    continue
                peer_ws = getattr(self, f"_ws_{peer_id}", None)
                if peer_ws:
                    try:
                        await peer_ws.send_json(message)
                    except Exception as e:
                        logger.warning(f"Failed to send to peer {peer_id}: {e}")


signaling = WebRTCSignaling()
