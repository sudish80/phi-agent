from backend.calling.manager import CallManager
from backend.calling.signaling import WebRTCSignaling

call_manager = CallManager()
webrtc_signaling = WebRTCSignaling()

__all__ = ["CallManager", "WebRTCSignaling", "call_manager", "webrtc_signaling"]
