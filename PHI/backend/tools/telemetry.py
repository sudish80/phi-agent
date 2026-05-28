"""Telemetry Engine — Real-time tool usage tracking, latency monitoring, and live streaming.

Records every tool execution with:
  - Timestamp, tool name, session ID
  - Duration (ms)
  - Success/failure + error message
  - Arguments (sanitized)

Exposes aggregated stats (min/max/avg/p95) and WebSocket streaming.
"""

import json
import time
import logging
import threading
import sqlite3
import asyncio
from typing import Dict, Any, List, Optional, Callable
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / "telemetry.db"
_local = threading.local()

# In-memory ring buffer for recent telemetry events (last 10000)
_RECENT_EVENTS: deque = deque(maxlen=10000)

# WebSocket subscribers for live streaming
_WS_SUBSCRIBERS: List[Callable] = []

# Aggregated stats (reset on read)
_stats_lock = threading.Lock()
_agg_stats = {
    "total_calls": 0,
    "total_errors": 0,
    "by_tool": defaultdict(lambda: {"calls": 0, "errors": 0, "total_ms": 0, "min_ms": float("inf"), "max_ms": 0}),
    "by_category": defaultdict(lambda: {"calls": 0, "errors": 0, "total_ms": 0}),
    "by_session": defaultdict(lambda: {"calls": 0, "errors": 0}),
}


def _get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
        _init_db()
    return _local.conn


def _init_db():
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            category TEXT DEFAULT '',
            session_id TEXT DEFAULT '',
            duration_ms REAL NOT NULL,
            success INTEGER NOT NULL DEFAULT 1,
            error_message TEXT DEFAULT '',
            args_snippet TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_tool_calls_timestamp ON tool_calls(timestamp);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_tool ON tool_calls(tool_name);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
        CREATE TABLE IF NOT EXISTS telemetry_hourly (
            hour TEXT PRIMARY KEY,
            total_calls INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            avg_duration_ms REAL DEFAULT 0,
            p95_duration_ms REAL DEFAULT 0,
            by_tool TEXT DEFAULT '{}',
            by_category TEXT DEFAULT '{}'
        );
    """)
    db.commit()


def record_tool_call(tool_name: str, category: str, duration_ms: float,
                     success: bool = True, error_message: str = "",
                     session_id: str = "", args: Dict = None):
    """Record a tool execution event."""
    now = datetime.now(timezone.utc).isoformat()
    args_snippet = json.dumps(args)[:200] if args else ""

    # In-memory ring buffer
    event = {
        "timestamp": now, "tool": tool_name, "category": category,
        "session": session_id, "duration_ms": round(duration_ms, 2),
        "success": success, "error": error_message,
    }
    _RECENT_EVENTS.append(event)

    # Aggregated stats
    with _stats_lock:
        _agg_stats["total_calls"] += 1
        if not success:
            _agg_stats["total_errors"] += 1
        bt = _agg_stats["by_tool"][tool_name]
        bt["calls"] += 1
        bt["total_ms"] += duration_ms
        bt["min_ms"] = min(bt["min_ms"], duration_ms)
        bt["max_ms"] = max(bt["max_ms"], duration_ms)
        if not success:
            bt["errors"] += 1
        bc = _agg_stats["by_category"][category]
        bc["calls"] += 1
        bc["total_ms"] += duration_ms
        if not success:
            bc["errors"] += 1
        bs = _agg_stats["by_session"][session_id]
        bs["calls"] += 1
        if not success:
            bs["errors"] += 1

    # Persist to SQLite (async via fire-and-forget thread)
    t = threading.Thread(target=_persist_call, args=(
        now, tool_name, category, session_id, duration_ms, success, error_message, args_snippet
    ), daemon=True)
    t.start()

    # Notify WebSocket subscribers
    _notify_subscribers(event)


def _persist_call(now, tool_name, category, session_id, duration_ms, success, error_message, args_snippet):
    try:
        db = _get_db()
        db.execute(
            "INSERT INTO tool_calls (timestamp, tool_name, category, session_id, duration_ms, success, error_message, args_snippet) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (now, tool_name, category, session_id, duration_ms, 1 if success else 0, error_message, args_snippet)
        )
        db.commit()
    except Exception as e:
        logger.error(f"Failed to persist telemetry: {e}")


def _notify_subscribers(event: dict):
    """Push event to all WebSocket subscribers."""
    dead = []
    for cb in _WS_SUBSCRIBERS:
        try:
            cb(event)
        except Exception:
            dead.append(cb)
    for cb in dead:
        try:
            _WS_SUBSCRIBERS.remove(cb)
        except ValueError:
            pass


def subscribe(callback: Callable) -> Callable:
    """Subscribe to live telemetry events. Returns unsubscribe function."""
    _WS_SUBSCRIBERS.append(callback)
    def unsubscribe():
        try:
            _WS_SUBSCRIBERS.remove(callback)
        except ValueError:
            pass
    return unsubscribe


def get_stats(reset: bool = False) -> dict:
    """Get aggregated statistics since last reset."""
    global _agg_stats
    with _stats_lock:
        result = {
            "total_calls": _agg_stats["total_calls"],
            "total_errors": _agg_stats["total_errors"],
            "error_rate": round(_agg_stats["total_errors"] / max(_agg_stats["total_calls"], 1) * 100, 2),
            "by_tool": {},
            "by_category": {},
            "by_session": {},
        }
        for tool, data in _agg_stats["by_tool"].items():
            result["by_tool"][tool] = {
                "calls": data["calls"],
                "errors": data["errors"],
                "avg_ms": round(data["total_ms"] / max(data["calls"], 1), 2),
                "min_ms": round(data["min_ms"], 2) if data["min_ms"] != float("inf") else 0,
                "max_ms": round(data["max_ms"], 2),
            }
        for cat, data in _agg_stats["by_category"].items():
            result["by_category"][cat] = {
                "calls": data["calls"],
                "errors": data["errors"],
                "avg_ms": round(data["total_ms"] / max(data["calls"], 1), 2),
            }
        for sid, data in _agg_stats["by_session"].items():
            result["by_session"][sid] = {
                "calls": data["calls"],
                "errors": data["errors"],
            }
        if reset:
            _agg_stats = {
                "total_calls": 0, "total_errors": 0,
                "by_tool": defaultdict(lambda: {"calls": 0, "errors": 0, "total_ms": 0, "min_ms": float("inf"), "max_ms": 0}),
                "by_category": defaultdict(lambda: {"calls": 0, "errors": 0, "total_ms": 0}),
                "by_session": defaultdict(lambda: {"calls": 0, "errors": 0}),
            }
        return result


def get_history(limit: int = 100, tool: str = "", session: str = "", success: Optional[bool] = None) -> List[dict]:
    """Query historical telemetry data."""
    db = _get_db()
    conditions = []
    params = []
    if tool:
        conditions.append("tool_name = ?")
        params.append(tool)
    if session:
        conditions.append("session_id = ?")
        params.append(session)
    if success is not None:
        conditions.append("success = ?")
        params.append(1 if success else 0)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = db.execute(
        f"SELECT * FROM tool_calls WHERE {where} ORDER BY id DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    return [dict(r) for r in rows]


def get_hourly_summary(hours: int = 24) -> List[dict]:
    """Get hourly aggregated summaries."""
    db = _get_db()
    from datetime import datetime, timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = db.execute(
        "SELECT hour, total_calls, total_errors, avg_duration_ms, p95_duration_ms FROM telemetry_hourly WHERE hour > ? ORDER BY hour",
        (cutoff,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_slow_tools(min_calls: int = 5, threshold_ms: float = 1000) -> List[dict]:
    """Find tools with avg duration above threshold."""
    stats = get_stats()
    slow = []
    for tool, data in stats["by_tool"].items():
        if data["calls"] >= min_calls and data["avg_ms"] > threshold_ms:
            slow.append({"tool": tool, **data})
    return sorted(slow, key=lambda x: -x["avg_ms"])


def get_error_hotspots(min_errors: int = 3) -> List[dict]:
    """Find tools with high error rates."""
    stats = get_stats()
    hotspots = []
    for tool, data in stats["by_tool"].items():
        if data["errors"] >= min_errors:
            rate = round(data["errors"] / max(data["calls"], 1) * 100, 1)
            hotspots.append({"tool": tool, "error_rate": rate, **data})
    return sorted(hotspots, key=lambda x: -x["error_rate"])


def get_live_events(count: int = 50) -> List[dict]:
    """Return recent events from ring buffer."""
    return list(_RECENT_EVENTS)[-count:]


def instrument_agent(agent_instance):
    """Patch an agent instance to record telemetry for all tool executions."""
    original_execute = agent_instance.execute_tool

    async def instrumented_execute(tool_name: str, session_id: str = "", **kwargs):
        t0 = time.perf_counter()
        try:
            result = await original_execute(tool_name, session_id=session_id, **kwargs)
            duration_ms = (time.perf_counter() - t0) * 1000
            # Determine category from tool registry
            category = ""
            try:
                tool_def = agent_instance.tools.get(tool_name)
                if tool_def:
                    category = getattr(tool_def, "category", "") or tool_def.get("category", "")
            except Exception:
                pass
            record_tool_call(tool_name, category, duration_ms, success=True,
                           session_id=session_id, args=kwargs)
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            category = ""
            try:
                tool_def = agent_instance.tools.get(tool_name)
                if tool_def:
                    category = getattr(tool_def, "category", "") or tool_def.get("category", "")
            except Exception:
                pass
            record_tool_call(tool_name, category, duration_ms, success=False,
                           error_message=str(e), session_id=session_id, args=kwargs)
            raise

    agent_instance.execute_tool = instrumented_execute
    return agent_instance
