import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TelephonyProvider(ABC):
    """Base class for telephony providers (Twilio, Plivo, etc.)."""

    @abstractmethod
    async def make_call(self, to_number: str, twiml: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def send_sms(self, to: str, body: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def handle_incoming(self, request_data: Dict[str, Any]) -> str:
        ...


class TwilioProvider(TelephonyProvider):
    """Twilio telephony integration."""

    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None, from_number: Optional[str] = None):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized")
            except ImportError:
                logger.warning("twilio package not installed — using stub mode")
            except Exception as e:
                logger.error(f"Twilio init failed: {e}")

    async def make_call(self, to_number: str, twiml: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self._client:
            logger.info(f"[STUB] Twilio make_call to {to_number}")
            return {"status": "stub", "to": to_number, "sid": "STUB_CALL_SID"}

        try:
            call = self._client.calls.create(
                to=to_number,
                from_=from_number or self.from_number,
                twiml=twiml,
            )
            logger.info(f"Twilio call initiated: {call.sid}")
            return {"status": "initiated", "to": to_number, "sid": call.sid}
        except Exception as e:
            logger.error(f"Twilio make_call failed: {e}")
            return {"status": "error", "error": str(e)}

    async def send_sms(self, to: str, body: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self._client:
            logger.info(f"[STUB] Twilio send_sms to {to}: {body[:50]}...")
            return {"status": "stub", "to": to, "sid": "STUB_SMS_SID"}

        try:
            message = self._client.messages.create(
                to=to,
                from_=from_number or self.from_number,
                body=body,
            )
            logger.info(f"Twilio SMS sent: {message.sid}")
            return {"status": "sent", "to": to, "sid": message.sid}
        except Exception as e:
            logger.error(f"Twilio send_sms failed: {e}")
            return {"status": "error", "error": str(e)}

    async def handle_incoming(self, request_data: Dict[str, Any]) -> str:
        call_sid = request_data.get("CallSid", "unknown")
        from_number = request_data.get("From", "unknown")
        logger.info(f"Incoming call from {from_number} (SID: {call_sid})")
        return self._build_twiml_response(from_number)

    def _build_twiml_response(self, from_number: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello, this is your PHI assistant. How can I help you today?</Say>
    <Record timeout="10" transcribe="true" />
</Response>"""


class PlivoProvider(TelephonyProvider):
    """Plivo telephony integration (stub with same interface as Twilio)."""

    def __init__(self, auth_id: Optional[str] = None, auth_token: Optional[str] = None, from_number: Optional[str] = None):
        self.auth_id = auth_id
        self.auth_token = auth_token
        self.from_number = from_number
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.auth_id and self.auth_token:
            try:
                import plivo
                self._client = plivo.RestClient(auth_id=self.auth_id, auth_token=self.auth_token)
                logger.info("Plivo client initialized")
            except ImportError:
                logger.warning("plivo package not installed — using stub mode")
            except Exception as e:
                logger.error(f"Plivo init failed: {e}")

    async def make_call(self, to_number: str, twiml: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self._client:
            logger.info(f"[STUB] Plivo make_call to {to_number}")
            return {"status": "stub", "to": to_number, "request_uuid": "STUB"}
        logger.info(f"[STUB] Plivo make_call to {to_number} (client available)")
        return {"status": "initiated", "to": to_number, "request_uuid": "STUB_PLIVO"}

    async def send_sms(self, to: str, body: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self._client:
            logger.info(f"[STUB] Plivo send_sms to {to}: {body[:50]}...")
            return {"status": "stub", "to": to, "message_uuid": "STUB"}
        logger.info(f"[STUB] Plivo send_sms to {to}")
        return {"status": "sent", "to": to, "message_uuid": "STUB_PLIVO"}

    async def handle_incoming(self, request_data: Dict[str, Any]) -> str:
        from_number = request_data.get("From", "unknown")
        logger.info(f"Plivo incoming call from {from_number}")
        return "<Response><Speak>Hello from PHI assistant.</Speak></Response>"


class TelephonyManager:
    """Routes calls to the configured provider with rate limiting and logging."""

    def __init__(self, provider: Optional[TelephonyProvider] = None):
        self._provider = provider or TwilioProvider()
        self._call_log: List[Dict[str, Any]] = []
        self._rate_limit_max = 10
        self._rate_limit_window = 60.0
        self._call_timestamps: List[float] = []

    @property
    def provider(self) -> TelephonyProvider:
        return self._provider

    @provider.setter
    def provider(self, p: TelephonyProvider):
        self._provider = p
        logger.info(f"Telephony provider set to {type(p).__name__}")

    def _check_rate_limit(self) -> bool:
        now = time.time()
        self._call_timestamps = [t for t in self._call_timestamps if now - t < self._rate_limit_window]
        return len(self._call_timestamps) < self._rate_limit_max

    def _log_call(self, direction: str, to: str, status: str, details: str = ""):
        entry = {
            "direction": direction,
            "to": to,
            "status": status,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._call_log.append(entry)
        if len(self._call_log) > 1000:
            self._call_log = self._call_log[-500:]

    async def make_call(self, to_number: str, twiml: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded for outbound call")
            return {"status": "rate_limited", "to": to_number}
        self._call_timestamps.append(time.time())
        result = await self._provider.make_call(to_number, twiml, from_number)
        self._log_call("outbound", to_number, result.get("status", "unknown"))
        return result

    async def send_sms(self, to: str, body: str, from_number: Optional[str] = None) -> Dict[str, Any]:
        if not self._check_rate_limit():
            logger.warning("Rate limit exceeded for SMS")
            return {"status": "rate_limited", "to": to}
        self._call_timestamps.append(time.time())
        result = await self._provider.send_sms(to, body, from_number)
        self._log_call("sms", to, result.get("status", "unknown"), body[:100])
        return result

    async def handle_voice_webhook(self, request_data: Dict[str, Any]) -> str:
        return await self._provider.handle_incoming(request_data)

    def get_call_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self._call_log[-limit:]))


telephony_manager = TelephonyManager()
