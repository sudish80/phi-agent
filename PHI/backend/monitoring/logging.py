"""Structured logging with JSON output, session IDs, and levels."""

import json
import logging
import time
import sys
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class LogEvent:
    timestamp: float = 0.0
    level: str = "INFO"
    message: str = ""
    session_id: str = ""
    tool_name: str = ""
    duration_ms: float = 0.0
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t": self.timestamp or time.time(),
            "lvl": self.level,
            "msg": self.message,
            "sid": self.session_id or None,
            "tool": self.tool_name or None,
            "dur": self.duration_ms or None,
            **self.extras,
        }


class StructuredFormatter(logging.Formatter):
    """JSON formatter that includes structured fields."""

    def format(self, record: logging.LogRecord) -> str:
        log = LogEvent(
            timestamp=record.created,
            level=record.levelname,
            message=record.getMessage(),
        )
        if hasattr(record, 'session_id'):
            log.session_id = record.session_id
        if hasattr(record, 'tool_name'):
            log.tool_name = record.tool_name
        if hasattr(record, 'duration_ms'):
            log.duration_ms = record.duration_ms
        return json.dumps(log.to_dict())


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str, session_id: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if session_id:
        logger = logging.LoggerAdapter(logger, {"session_id": session_id})
    return logger
