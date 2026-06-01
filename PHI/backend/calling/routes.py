import json
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request

from backend.calling.models import CallState, MediaType
from backend.calling.manager import call_manager
from backend.calling.signaling import signaling as webrtc_signaling
from backend.calling.telephony import telephony_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Call Lifecycle
# ============================================================

@router.post("/api/calls/start")
async def start_call(payload: Dict[str, Any]):
    caller_id = payload.get("caller_id", "agent")
    callee_id = payload.get("callee_id", "")
    media_type_str = payload.get("media_type", "audio")
    sdp_offer = payload.get("sdp_offer", "")

    if not callee_id:
        raise HTTPException(status_code=400, detail="callee_id is required")

    try:
        media_type = MediaType(media_type_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid media_type: {media_type_str}")

    try:
        session = await call_manager.start_call(
            caller_id=caller_id,
            callee_id=callee_id,
            media_type=media_type,
            sdp_offer=sdp_offer,
        )
        return {"status": "ok", "session": session.to_dict()}
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/api/calls/{call_id}/accept")
async def accept_call(call_id: str, payload: Optional[Dict[str, Any]] = None):
    sdp_answer = (payload or {}).get("sdp_answer", "")
    session = await call_manager.accept_call(call_id, sdp_answer)
    if not session:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found or cannot be accepted")
    return {"status": "ok", "session": session.to_dict()}


@router.post("/api/calls/{call_id}/end")
async def end_call(call_id: str):
    session = await call_manager.end_call(call_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return {"status": "ok", "session": session.to_dict()}


@router.post("/api/calls/{call_id}/decline")
async def decline_call(call_id: str):
    session = await call_manager.decline_call(call_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return {"status": "ok", "session": session.to_dict()}


@router.post("/api/calls/{call_id}/mute")
async def mute_call(call_id: str):
    result = await call_manager.mute(call_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not active")
    return {"status": "ok", "muted": True}


@router.post("/api/calls/{call_id}/unmute")
async def unmute_call(call_id: str):
    result = await call_manager.unmute(call_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not active")
    return {"status": "ok", "muted": False}


@router.post("/api/calls/{call_id}/hold")
async def hold_call(call_id: str):
    result = await call_manager.hold(call_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not active or not connected")
    return {"status": "ok", "held": True}


@router.post("/api/calls/{call_id}/resume")
async def resume_call(call_id: str):
    result = await call_manager.resume(call_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not active or not held")
    return {"status": "ok", "held": False}


# ============================================================
# Call Queries
# ============================================================

@router.get("/api/calls/active")
async def list_active_calls():
    calls = await call_manager.get_active_calls()
    return {"status": "ok", "calls": [c.to_dict() for c in calls], "count": len(calls)}


@router.get("/api/calls/history")
async def call_history(session_id: Optional[str] = None, limit: int = 50):
    logs = await call_manager.get_call_history(session_id, limit)
    return {"status": "ok", "logs": [l.to_dict() for l in logs], "count": len(logs)}


@router.get("/api/calls/rooms")
async def list_rooms():
    rooms = await webrtc_signaling.list_rooms()
    return {"status": "ok", "rooms": rooms, "count": len(rooms)}


# ============================================================
# Telephony
# ============================================================

@router.post("/api/telephony/sms")
async def send_sms(payload: Dict[str, Any]):
    to = payload.get("to", "")
    body = payload.get("body", "")
    from_number = payload.get("from_number")

    if not to or not body:
        raise HTTPException(status_code=400, detail="to and body are required")

    result = await telephony_manager.send_sms(to, body, from_number)
    return {"status": "ok", "result": result}


@router.post("/api/telephony/voice")
async def voice_webhook(request: Request):
    form_data = await request.form()
    data = dict(form_data)
    twiml_response = await telephony_manager.handle_voice_webhook(data)
    from fastapi.responses import Response
    return Response(content=twiml_response, media_type="application/xml")


# ============================================================
# WebSocket — WebRTC Signaling
# ============================================================

@router.websocket("/ws/call/{room_id}")
async def websocket_call_signaling(websocket: WebSocket, room_id: str):
    peer_id = f"peer_{id(websocket)}"
    await websocket.accept()
    logger.info(f"WebSocket connected: peer={peer_id} room={room_id}")

    try:
        await webrtc_signaling.create_room(room_id)
    except ValueError:
        pass

    room_info = await webrtc_signaling.join_room(room_id, peer_id)

    await websocket.send_json({
        "type": "room_joined",
        "peer_id": peer_id,
        "peers": room_info.get("peers", []),
    })

    # Notify existing peers
    for existing_peer in room_info.get("peers", []):
        await webrtc_signaling.broadcast_to_room(room_id, {
            "type": "peer_joined",
            "peer_id": peer_id,
        }, exclude_peer=peer_id)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = message.get("type", "")

            if msg_type == "offer":
                sdp = message.get("sdp", "")
                session_id = message.get("session_id", room_id)
                await webrtc_signaling.create_offer(session_id, sdp)
                target = message.get("target")
                if target:
                    await webrtc_signaling.broadcast_to_room(room_id, {
                        "type": "offer",
                        "sdp": sdp,
                        "session_id": session_id,
                        "from": peer_id,
                    }, exclude_peer=peer_id)
                await websocket.send_json({"type": "offer_ack", "session_id": session_id})

            elif msg_type == "answer":
                sdp = message.get("sdp", "")
                session_id = message.get("session_id", room_id)
                await webrtc_signaling.handle_answer(session_id, sdp)
                target = message.get("target")
                if target:
                    await webrtc_signaling.broadcast_to_room(room_id, {
                        "type": "answer",
                        "sdp": sdp,
                        "session_id": session_id,
                        "from": peer_id,
                    }, exclude_peer=peer_id)

            elif msg_type == "ice_candidate":
                candidate = message.get("candidate", {})
                session_id = message.get("session_id", room_id)
                await webrtc_signaling.add_ice_candidate(session_id, candidate)
                target = message.get("target")
                if target:
                    await webrtc_signaling.broadcast_to_room(room_id, {
                        "type": "ice_candidate",
                        "candidate": candidate,
                        "session_id": session_id,
                        "from": peer_id,
                    }, exclude_peer=peer_id)

            elif msg_type == "end_call":
                session_id = message.get("session_id", room_id)
                await call_manager.end_call(session_id)
                await webrtc_signaling.broadcast_to_room(room_id, {
                    "type": "call_ended",
                    "session_id": session_id,
                    "from": peer_id,
                }, exclude_peer=peer_id)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({"type": "error", "detail": f"Unknown message type: {msg_type}"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: peer={peer_id} room={room_id}")
    except Exception as e:
        logger.error(f"WebSocket error peer={peer_id}: {e}")
    finally:
        await webrtc_signaling.leave_room(room_id, peer_id)
        await webrtc_signaling.broadcast_to_room(room_id, {
            "type": "peer_left",
            "peer_id": peer_id,
        }, exclude_peer=peer_id)

        peer_count = await webrtc_signaling.get_peer_count(room_id)
        if peer_count == 0:
            logger.info(f"No peers left in room {room_id}, cleaning up sessions")
            rooms = await webrtc_signaling.list_rooms()
            for room in rooms:
                if room.get("room_id") == room_id:
                    active_calls = await call_manager.get_active_calls()
                    for session in active_calls:
                        if session.id.startswith(room_id[:8]):
                            await call_manager.end_call(session.id)
