"""AlertManager — centralized alert dispatch and notification."""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert rules and dispatches notifications to registered handlers."""

    def __init__(self):
        self._handlers: List[Callable[[Dict[str, Any]], None]] = []
        self._alerts: List[Dict[str, Any]] = []
        self._max_alerts = 500

    def register_handler(self, handler: Callable[[Dict[str, Any]], None]):
        self._handlers.append(handler)
        logger.debug("Alert handler registered: %s", getattr(handler, "__name__", "anonymous"))

    def remove_handler(self, handler: Callable[[Dict[str, Any]], None]):
        self._handlers = [h for h in self._handlers if h is not handler]

    def send_alert(self, level: str, source: str, message: str, details: Optional[Dict] = None):
        alert = {
            "timestamp": time.time(),
            "level": level,
            "source": source,
            "message": message,
            "details": details or {},
        }
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        log_level = getattr(logging, level.upper(), logging.WARNING)
        logger.log(log_level, "ALERT [%s] %s: %s", source, level, message)

        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.warning("Alert handler %s failed: %s",
                              getattr(handler, "__name__", "anonymous"), e)

    def info(self, source: str, message: str, details: Optional[Dict] = None):
        self.send_alert("info", source, message, details)

    def warning(self, source: str, message: str, details: Optional[Dict] = None):
        self.send_alert("warning", source, message, details)

    def error(self, source: str, message: str, details: Optional[Dict] = None):
        self.send_alert("error", source, message, details)

    def critical(self, source: str, message: str, details: Optional[Dict] = None):
        self.send_alert("critical", source, message, details)

    def get_alerts(self, limit: int = 50, level: Optional[str] = None) -> List[Dict[str, Any]]:
        alerts = self._alerts
        if level:
            alerts = [a for a in alerts if a["level"] == level]
        return alerts[-limit:]

    def get_stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for a in self._alerts:
            counts[a["level"]] = counts.get(a["level"], 0) + 1
        return {
            "total": len(self._alerts),
            "by_level": counts,
        }

    def clear(self):
        self._alerts.clear()
        logger.info("Alert history cleared")


alert_manager = AlertManager()
