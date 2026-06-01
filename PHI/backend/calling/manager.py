import json
import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone

from backend.calling.models import CallSession, CallState, CallLog, MediaType
from backend.calling.signaling import signaling as webrtc_signaling
from backend.calling.vad import vad_registry, VADConfig

logger = logging.getLogger(__name__)


class CallManager:
    """Manages the full lifecycle of calls — start, end, accept, decline, mute, hold."""

    def __init__(self):
        self._active_calls: Dict[str, CallSession] = {}
        self._call_logs: Dict[str, List[CallLog]] = {}
        self._muted_calls: set = set()
        self._held_calls: set = set()
        self._incoming_queue: List[CallSession] = []
        self._hooks: Dict[str, List[Callable]] = {
            "on_call_start": [],
            "on_call_end": [],
            "on_call_accept": [],
            "on_call_decline": [],
            "on_mute": [],
            "on_unmute": [],
            "on_hold": [],
            "on_resume": [],
        }
        self._lock = asyncio.Lock()
        self._max_concurrent_calls = 4

    def register_hook(self, event: str, callback: Callable):
        if event in self._hooks:
            self._hooks[event].append(callback)

    def _emit(self, event: str, **kwargs):
        for cb in self._hooks.get(event, []):
            try:
                cb(**kwargs)
            except Exception as e:
                logger.warning(f"Hook {event} error: {e}")

    def _log_event(self, session_id: str, event: str, details: str = ""):
        log_entry = CallLog(session_id=session_id, event=event, details=details)
        if session_id not in self._call_logs:
            self._call_logs[session_id] = []
        self._call_logs[session_id].append(log_entry)
        logger.info(f"[{session_id[:8]}] {event}: {details}")
        return log_entry

    async def start_call(
        self,
        caller_id: str,
        callee_id: str,
        media_type: MediaType = MediaType.audio,
        sdp_offer: str = "",
    ) -> CallSession:
        async with self._lock:
            active_count = sum(1 for s in self._active_calls.values() if s.state == CallState.connected)
            if active_count >= self._max_concurrent_calls:
                raise RuntimeError(f"Max concurrent calls reached ({self._max_concurrent_calls})")

            session = CallSession(
                caller_id=caller_id,
                callee_id=callee_id,
                state=CallState.ringing,
                start_time=datetime.now(timezone.utc).isoformat(),
                media_type=media_type,
            )
            if sdp_offer:
                session.sdp_offer = sdp_offer
                session.state = CallState.connecting

            self._active_calls[session.id] = session
            await webrtc_signaling.create_offer(session.id, sdp_offer)

        self._incoming_queue.append(session)
        self._log_event(session.id, "call_started", f"{caller_id} -> {callee_id}")
        self._emit("on_call_start", session=session)
        return session

    async def accept_call(self, session_id: str, sdp_answer: str = "") -> Optional[CallSession]:
        async with self._lock:
            session = self._active_calls.get(session_id)
            if not session:
                logger.warning(f"Call {session_id} not found")
                return None
            if session.state not in (CallState.ringing, CallState.connecting):
                logger.warning(f"Call {session_id} cannot be accepted (state={session.state})")
                return None

            session.state = CallState.connected
            if sdp_answer:
                session.sdp_answer = sdp_answer
            self._incoming_queue = [s for s in self._incoming_queue if s.id != session_id]

        self._log_event(session_id, "call_accepted", f"accepted by {session.callee_id}")
        self._emit("on_call_accept", session=session)
        await webrtc_signaling.handle_answer(session_id, sdp_answer)
        return session

    async def decline_call(self, session_id: str) -> Optional[CallSession]:
        async with self._lock:
            session = self._active_calls.get(session_id)
            if not session:
                return None
            session.state = CallState.declined
            session.end_time = datetime.now(timezone.utc).isoformat()
            self._incoming_queue = [s for s in self._incoming_queue if s.id != session_id]

        self._log_event(session_id, "call_declined", f"declined by {session.callee_id}")
        self._emit("on_call_decline", session=session)
        await webrtc_signaling.end_session(session_id)
        return session

    async def end_call(self, session_id: str) -> Optional[CallSession]:
        async with self._lock:
            session = self._active_calls.get(session_id)
            if not session:
                return None
            session.state = CallState.ended
            session.end_time = datetime.now(timezone.utc).isoformat()
            if session.start_time:
                start = datetime.fromisoformat(session.start_time)
                end = datetime.fromisoformat(session.end_time)
                session.duration_sec = (end - start).total_seconds()
            self._muted_calls.discard(session_id)
            self._held_calls.discard(session_id)
            stale_session = self._active_calls.pop(session_id, None)

        self._log_event(session_id, "call_ended", f"duration={session.duration_sec:.1f}s")
        self._emit("on_call_end", session=session)
        vad_registry.remove(session_id)

        if stale_session and stale_session.media_type == MediaType.audio:
            await self._save_recording(stale_session)

        await webrtc_signaling.end_session(session_id)
        return session

    async def mute(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._active_calls:
                return False
            self._muted_calls.add(session_id)
        self._log_event(session_id, "muted", "Microphone muted")
        self._emit("on_mute", session_id=session_id)
        return True

    async def unmute(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._active_calls:
                return False
            self._muted_calls.discard(session_id)
        self._log_event(session_id, "unmuted", "Microphone unmuted")
        self._emit("on_unmute", session_id=session_id)
        return True

    async def hold(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._active_calls:
                return False
            session = self._active_calls[session_id]
            if session.state != CallState.connected:
                return False
            self._held_calls.add(session_id)
        self._log_event(session_id, "held", "Call placed on hold")
        self._emit("on_hold", session_id=session_id)
        return True

    async def resume(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._active_calls:
                return False
            self._held_calls.discard(session_id)
        self._log_event(session_id, "resumed", "Call resumed from hold")
        self._emit("on_resume", session_id=session_id)
        return True

    async def is_muted(self, session_id: str) -> bool:
        return session_id in self._muted_calls

    async def is_held(self, session_id: str) -> bool:
        return session_id in self._held_calls

    async def get_active_calls(self) -> List[CallSession]:
        async with self._lock:
            return list(self._active_calls.values())

    async def get_call(self, session_id: str) -> Optional[CallSession]:
        async with self._lock:
            return self._active_calls.get(session_id)

    async def get_pending_incoming(self) -> List[CallSession]:
        return [s for s in self._incoming_queue if s.state in (CallState.ringing,)]

    async def get_call_history(self, session_id: Optional[str] = None, limit: int = 50) -> List[CallLog]:
        if session_id:
            logs = self._call_logs.get(session_id, [])
            return logs[-limit:]
        all_logs = []
        for logs in self._call_logs.values():
            all_logs.extend(logs)
        all_logs.sort(key=lambda x: x.timestamp, reverse=True)
        return all_logs[:limit]

    async def _save_recording(self, session: CallSession):
        try:
            from backend.audio.audio_manager import AudioManager
            audio_mgr = AudioManager()
            await audio_mgr.initialize()
            metadata = {
                "session_id": session.id,
                "caller_id": session.caller_id,
                "callee_id": session.callee_id,
                "duration_sec": session.duration_sec,
                "media_type": session.media_type.value,
            }
            logger.info(f"Recording metadata saved for session {session.id[:8]}")
        except Exception as e:
            logger.warning(f"Failed to save recording for {session.id[:8]}: {e}")


call_manager = CallManager()
