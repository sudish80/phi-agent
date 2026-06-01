"""Alert system for the PHI AI agent.

Provides alert severity levels, structured alert dataclass, and an AlertManager
singleton that dispatches alerts to console, webhook, email, and WebSocket
channels. Supports acknowledgment, resolution, filtering, and auto-resolution.
"""

import os
import json
import uuid
import time
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class AlertSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    id: str
    severity: AlertSeverity
    source: str
    message: str
    detail: str = ""
    timestamp: str = ""
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[str] = None
    acknowledged_at: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "source": self.source,
            "message": self.message,
            "detail": self.detail,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "acknowledged_at": self.acknowledged_at,
        }


AlertHandler = Callable[[Alert], None]


class AlertManager:
    """Singleton alert manager with multi-channel dispatch."""

    _instance: Optional["AlertManager"] = None

    def __new__(cls) -> "AlertManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._alerts: List[Alert] = []
        self._handlers: List[AlertHandler] = []
        self._webhook_url: Optional[str] = None
        self._email_config: Optional[Dict] = None
        self._ws_callbacks: List[Callable] = []
        self._max_alerts: int = 10000
        self._auto_resolve_task: Optional[asyncio.Task] = None
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers.append(self._console_handler)

    def _console_handler(self, alert: Alert) -> None:
        sev = alert.severity.value.upper()
        log_msg = f"[{sev}] [{alert.source}] {alert.message}"
        if alert.detail:
            log_msg += f" — {alert.detail}"
        if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.ERROR):
            logger.error(log_msg)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(log_msg)
        elif alert.severity == AlertSeverity.DEBUG:
            logger.debug(log_msg)
        else:
            logger.info(log_msg)

    def configure_webhook(self, url: str) -> None:
        self._webhook_url = url
        self._handlers.append(self._webhook_handler)
        logger.info("Alert webhook configured: %s", url)

    def configure_email(self, smtp_server: str, smtp_port: int,
                        username: str, password: str,
                        from_addr: str, to_addrs: List[str]) -> None:
        self._email_config = {
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
            "from_addr": from_addr,
            "to_addrs": to_addrs,
        }
        self._handlers.append(self._email_handler)
        logger.info("Alert email configured: %s -> %s", from_addr, to_addrs)

    def register_ws_callback(self, callback: Callable) -> None:
        self._ws_callbacks.append(callback)

    def unregister_ws_callback(self, callback: Callable) -> None:
        self._ws_callbacks.remove(callback)

    async def send_alert(self, severity: AlertSeverity, source: str,
                         message: str, detail: str = "") -> Alert:
        alert = Alert(
            id=str(uuid.uuid4()),
            severity=severity,
            source=source,
            message=message,
            detail=detail,
        )
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error("Alert handler %s failed: %s", handler.__name__, e)

        for cb in self._ws_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(alert.to_dict())
                else:
                    cb(alert.to_dict())
            except Exception as e:
                logger.error("Alert WS callback failed: %s", e)

        return alert

    async def _webhook_handler(self, alert: Alert) -> None:
        if not self._webhook_url:
            return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self._webhook_url,
                    json=alert.to_dict(),
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except ImportError:
            logger.warning("aiohttp not available for webhook alert")
        except Exception as e:
            logger.warning("Webhook alert delivery failed: %s", e)

    async def _email_handler(self, alert: Alert) -> None:
        if not self._email_config:
            return
        import smtplib
        from email.mime.text import MIMEText
        try:
            cfg = self._email_config
            subject = f"[{alert.severity.value.upper()}] PHI Alert: {alert.message}"
            body = f"Source: {alert.source}\nSeverity: {alert.severity.value}\nTime: {alert.timestamp}\n\n{alert.message}\n\n{alert.detail}"
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = cfg["from_addr"]
            msg["To"] = ", ".join(cfg["to_addrs"])
            with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
                server.starttls()
                server.login(cfg["username"], cfg["password"])
                server.send_message(msg)
        except Exception as e:
            logger.warning("Email alert delivery failed: %s", e)

    def acknowledge(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def resolve(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def dismiss(self, alert_id: str) -> bool:
        initial_len = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.id != alert_id]
        return len(self._alerts) < initial_len

    def get_alerts(self, severity: Optional[AlertSeverity] = None,
                   source: Optional[str] = None,
                   since: Optional[str] = None,
                   resolved: Optional[bool] = None,
                   limit: int = 100) -> List[Alert]:
        results = list(self._alerts)
        if severity:
            results = [a for a in results if a.severity == severity]
        if source:
            results = [a for a in results if a.source == source]
        if since:
            results = [a for a in results if a.timestamp >= since]
        if resolved is not None:
            results = [a for a in results if a.resolved == resolved]
        results.reverse()
        return results[:limit]

    def get_unresolved(self) -> List[Alert]:
        return [a for a in self._alerts if not a.resolved]

    async def auto_resolve(self, after_seconds: int = 3600) -> None:
        while True:
            try:
                now = datetime.now(timezone.utc)
                for alert in self._alerts:
                    if alert.resolved:
                        continue
                    try:
                        alert_time = datetime.fromisoformat(alert.timestamp)
                        if (now - alert_time).total_seconds() > after_seconds:
                            alert.resolved = True
                            alert.resolved_at = now.isoformat()
                            logger.info("Auto-resolved alert %s (%s)", alert.id[:8], alert.message[:60])
                    except (ValueError, TypeError):
                        continue
            except Exception as e:
                logger.error("Auto-resolve error: %s", e)
            await asyncio.sleep(after_seconds // 4)

    def start_background(self, after_seconds: int = 3600) -> None:
        if self._auto_resolve_task and not self._auto_resolve_task.done():
            return
        self._auto_resolve_task = asyncio.create_task(self.auto_resolve(after_seconds))
        logger.info("Alert auto-resolve started (after %ds)", after_seconds)

    def stop_background(self) -> None:
        if self._auto_resolve_task and not self._auto_resolve_task.done():
            self._auto_resolve_task.cancel()
            self._auto_resolve_task = None
            logger.info("Alert auto-resolve stopped")


alert_manager = AlertManager()
