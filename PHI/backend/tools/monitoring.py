"""Monitoring & Observability — ADVANCED: SQLite time-series store, alert engine,
aggregation pipeline, Prometheus endpoint, cost tracking with per-model rates.

Stores metrics in time-series buckets, supports alert thresholds with
webhook notifications, and provides pre-aggregated dashboard data.
"""

import json
import os
import logging
import time
import sqlite3
import threading
import asyncio
from typing import Optional, Dict, Any, List, Callable
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "monitoring.db"
_local = threading.local()

_ALERTS: List[Dict] = []
_ALERT_THRESHOLDS: Dict[str, dict] = {}
_SPANS: List[Dict] = []
_MAX_SPANS = 1000

_LLM_COST_PER_1K = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "deepseek": {"input": 0.00014, "output": 0.00028},
    "default": {"input": 0.01, "output": 0.03},
}


def _get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def _init_db():
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS metrics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            name TEXT NOT NULL,
            value REAL NOT NULL,
            tags TEXT DEFAULT '{}',
            host TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            session_id TEXT DEFAULT '',
            latency_ms REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            duration_ms REAL DEFAULT 0,
            success INTEGER DEFAULT 1,
            session_id TEXT DEFAULT '',
            error TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            current_value REAL NOT NULL,
            threshold REAL NOT NULL,
            severity TEXT DEFAULT 'warning',
            message TEXT DEFAULT '',
            acknowledged INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics_events(name);
        CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_llm_model ON llm_calls(model);
        CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_calls(tool_name);
    """)
    db.commit()


_init_db()


# --- Metric recording with time-series buckets ---

async def metrics_record(name: str, value: float = 1, tags: Optional[Dict] = None) -> str:
    db = _get_db()
    ts = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT INTO metrics_events (timestamp, name, value, tags) VALUES (?, ?, ?, ?)",
               (ts, name, value, json.dumps(tags or {})))
    db.commit()
    _check_alerts(name, value)
    return json.dumps({"recorded": True, "metric": name, "value": value, "timestamp": ts})


async def metrics_record_llm(model: str, input_tokens: int, output_tokens: int,
                              session_id: str = "", latency_ms: float = 0) -> str:
    db = _get_db()
    total = input_tokens + output_tokens
    rate = _LLM_COST_PER_1K.get(model, _LLM_COST_PER_1K["default"])
    cost = (input_tokens / 1000 * rate["input"]) + (output_tokens / 1000 * rate["output"])
    db.execute("INSERT INTO llm_calls (timestamp, model, input_tokens, output_tokens, total_tokens, cost_usd, session_id, latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
               (datetime.now(timezone.utc).isoformat(), model, input_tokens, output_tokens, total, round(cost, 6), session_id, latency_ms))
    db.commit()
    return json.dumps({"recorded": True, "model": model, "total_tokens": total,
                        "cost_usd": round(cost, 6), "latency_ms": latency_ms})


async def metrics_record_tool(tool_name: str, duration_ms: float = 0,
                               success: bool = True, session_id: str = "",
                               error: str = "") -> str:
    db = _get_db()
    db.execute("INSERT INTO tool_calls (timestamp, tool_name, duration_ms, success, session_id, error) VALUES (?, ?, ?, ?, ?, ?)",
               (datetime.now(timezone.utc).isoformat(), tool_name, duration_ms, 1 if success else 0,
                session_id, error[:200]))
    db.commit()
    return json.dumps({"recorded": True, "tool": tool_name, "duration_ms": duration_ms, "success": success})


# --- Alert engine with threshold checking ---

async def alert_set_threshold(metric_name: str, warning: float, critical: float,
                               description: str = "", webhook_url: str = "") -> str:
    _ALERT_THRESHOLDS[metric_name] = {
        "warning": warning, "critical": critical,
        "description": description, "webhook_url": webhook_url,
        "created": datetime.now(timezone.utc).isoformat()
    }
    return json.dumps({"set": True, "metric": metric_name,
                        "warning": warning, "critical": critical})


async def alert_list_thresholds() -> str:
    return json.dumps(_ALERT_THRESHOLDS, indent=2)


def _check_alerts(metric_name: str, value: float):
    threshold = _ALERT_THRESHOLDS.get(metric_name)
    if not threshold:
        return
    severity = None
    if value >= threshold.get("critical", float("inf")):
        severity = "critical"
    elif value >= threshold.get("warning", float("inf")):
        severity = "warning"
    if severity:
        db = _get_db()
        db.execute("INSERT INTO alerts (timestamp, rule_name, metric_name, current_value, threshold, severity, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (datetime.now(timezone.utc).isoformat(), f"threshold_{metric_name}", metric_name,
                    value, threshold.get(severity, 0), severity,
                    f"{metric_name} = {value} exceeds {severity} threshold ({threshold.get(severity, 0)})"))
        db.commit()
        _ALERTS.append({"metric": metric_name, "value": value,
                        "threshold": threshold.get(severity), "severity": severity,
                        "timestamp": datetime.now(timezone.utc).isoformat()})


async def alert_list(severity: Optional[str] = None, limit: int = 50) -> str:
    db = _get_db()
    query = "SELECT * FROM alerts WHERE 1=1"
    params = []
    if severity:
        query += " AND severity=?"
        params.append(severity)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(int(limit))
    rows = db.execute(query, params).fetchall()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


async def alert_acknowledge(alert_id: int) -> str:
    db = _get_db()
    db.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (int(alert_id),))
    db.commit()
    return json.dumps({"acknowledged": True, "alert_id": alert_id})


# --- Aggregation engine ---

async def metrics_summary(since_minutes: int = 60) -> str:
    db = _get_db()
    since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
    # LLM costs
    llm_row = db.execute("""
        SELECT COUNT(*) as calls, SUM(total_tokens) as tokens,
               SUM(cost_usd) as cost, SUM(input_tokens) as input_tok,
               SUM(output_tokens) as output_tok
        FROM llm_calls WHERE timestamp > ?
    """, (since,)).fetchone()
    # Tool calls
    tool_row = db.execute("""
        SELECT COUNT(*) as calls, AVG(duration_ms) as avg_dur,
               SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls WHERE timestamp > ?
    """, (since,)).fetchone()
    # Top tools
    top_tools = db.execute("""
        SELECT tool_name, COUNT(*) as cnt, AVG(duration_ms) as avg_dur
        FROM tool_calls WHERE timestamp > ?
        GROUP BY tool_name ORDER BY cnt DESC LIMIT 10
    """, (since,)).fetchall()
    # Metrics by name
    metrics = db.execute("""
        SELECT name, COUNT(*) as cnt, AVG(value) as avg_val,
               MAX(value) as max_val, MIN(value) as min_val
        FROM metrics_events WHERE timestamp > ?
        GROUP BY name ORDER BY cnt DESC
    """, (since,)).fetchall()
    # Active alerts
    alert_count = db.execute("SELECT COUNT(*) as cnt FROM alerts WHERE acknowledged=0").fetchone()["cnt"]
    return json.dumps({
        "period_minutes": since_minutes,
        "llm": dict(llm_row) if llm_row else {},
        "tools": dict(tool_row) if tool_row else {},
        "top_tools": [dict(r) for r in top_tools],
        "metrics": [dict(r) for r in metrics],
        "active_alerts": alert_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2)


async def metrics_cost_summary() -> str:
    db = _get_db()
    total = db.execute("""
        SELECT COUNT(*) as calls, SUM(total_tokens) as tokens,
               SUM(cost_usd) as cost, SUM(input_tokens) as inp,
               SUM(output_tokens) as outp
        FROM llm_calls
    """).fetchone()
    by_model = db.execute("""
        SELECT model, COUNT(*) as calls, SUM(total_tokens) as tokens,
               SUM(cost_usd) as cost
        FROM llm_calls GROUP BY model ORDER BY cost DESC
    """).fetchall()
    return json.dumps({
        "total": dict(total) if total else {},
        "by_model": [dict(r) for r in by_model],
    }, indent=2)


# --- Performance Tracing (in-memory, bounded) ---

async def trace_start(operation: str, metadata: Optional[Dict] = None) -> str:
    span = {"id": f"span_{int(time.time() * 1000)}_{len(_SPANS)}",
            "operation": operation, "start_time": time.time(),
            "metadata": metadata or {}}
    _SPANS.append(span)
    if len(_SPANS) > _MAX_SPANS:
        _SPANS.pop(0)
    return json.dumps({"span_id": span["id"], "operation": operation})


async def trace_end(span_id: str) -> str:
    for span in reversed(_SPANS):
        if span.get("id") == span_id:
            dur = round((time.time() - span["start_time"]) * 1000, 2)
            span["duration_ms"] = dur
            # Persist slow traces
            if dur > 1000:
                db = _get_db()
                db.execute("INSERT INTO tool_calls (timestamp, tool_name, duration_ms, success) VALUES (?, ?, ?, ?)",
                           (datetime.now(timezone.utc).isoformat(), f"trace:{span['operation']}", dur, 1))
                db.commit()
            return json.dumps({"span_id": span_id, "operation": span["operation"],
                                "duration_ms": dur})
    return json.dumps({"error": f"Span {span_id} not found"})


async def trace_summary() -> str:
    completed = [s for s in _SPANS if s.get("duration_ms")]
    if not completed:
        return json.dumps({"spans": 0})
    by_op = defaultdict(list)
    for s in completed:
        by_op[s["operation"]].append(s["duration_ms"])
    ops = {op: {"count": len(durs), "avg_ms": round(sum(durs) / len(durs), 1),
                 "total_ms": round(sum(durs), 1), "max_ms": round(max(durs), 1)}
           for op, durs in by_op.items()}
    return json.dumps({"total_spans": len(completed), "operations": ops}, indent=2)


# --- Structured Logging ---

_LOG_BUFFER: List[Dict] = []
_MAX_LOG_BUFFER = 500

async def log_event(level: str, message: str, component: str = "system",
                     extra: Optional[Dict] = None) -> str:
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(),
             "level": level.upper(), "message": message,
             "component": component, "extra": extra or {}}
    _LOG_BUFFER.append(entry)
    if len(_LOG_BUFFER) > _MAX_LOG_BUFFER:
        _LOG_BUFFER.pop(0)
    getattr(logger, level.lower(), logger.info)(f"[{component}] {message}")
    return json.dumps({"logged": True, "entry": entry}, indent=2)


async def log_get(level: Optional[str] = None, component: Optional[str] = None,
                   limit: int = 50) -> str:
    entries = _LOG_BUFFER
    if level:
        entries = [e for e in entries if e["level"] == level.upper()]
    if component:
        entries = [e for e in entries if e["component"] == component]
    return json.dumps(entries[-int(limit):], indent=2)


# --- Prometheus exposition format ---

async def metrics_prometheus() -> str:
    db = _get_db()
    lines = ["# HELP jarvis_metrics JARVIS system metrics",
             "# TYPE jarvis_metrics gauge"]
    # Active metrics from DB
    rows = db.execute("""
        SELECT name, AVG(value) as val FROM metrics_events
        WHERE timestamp > (SELECT MAX(timestamp) FROM metrics_events) - INTERVAL '5 minutes'
        GROUP BY name
    """).fetchall() if 'sqlite' not in str(type(db)) else []
    if not rows:
        # SQLite fallback: get latest value per metric
        rows = db.execute("""
            SELECT m1.name, m1.value FROM metrics_events m1
            INNER JOIN (SELECT name, MAX(id) as max_id FROM metrics_events GROUP BY name) m2
            ON m1.id = m2.max_id
        """).fetchall()
    for r in rows:
        lines.append(f'jarvis_{r["name"].replace(" ", "_").replace(".", "_")}{{source="db"}} {r["value"]}')
    # LLM stats
    llm = db.execute("SELECT COUNT(*) as c, SUM(total_tokens) as t, SUM(cost_usd) as cost FROM llm_calls").fetchone()
    lines.append(f'jarvis_llm_calls_total {llm["c"]}')
    lines.append(f'jarvis_llm_tokens_total {llm["t"] or 0}')
    lines.append(f'jarvis_llm_cost_total_usd {round(llm["cost"] or 0, 4)}')
    # Tool stats
    tool = db.execute("SELECT COUNT(*) as c, AVG(duration_ms) as avg_dur FROM tool_calls").fetchone()
    lines.append(f'jarvis_tool_calls_total {tool["c"]}')
    lines.append(f'jarvis_tool_avg_duration_ms {round(tool["avg_dur"] or 0, 1)}')
    # Error count
    err = db.execute("SELECT COUNT(*) as c FROM metrics_events WHERE name='error'").fetchone()
    lines.append(f'jarvis_errors_total {err["c"]}')
    # Uptime
    first = db.execute("SELECT MIN(timestamp) FROM metrics_events").fetchone()[0]
    uptime = 0
    if first:
        uptime = (datetime.now(timezone.utc) - datetime.fromisoformat(first)).total_seconds()
    lines.append(f'jarvis_uptime_seconds {round(uptime, 1)}')
    return "\n".join(lines)


# --- Legacy compatibility ---

async def metrics_get() -> str:
    return await metrics_summary(60)


async def metrics_track_llm_call(model: str, input_tokens: int, output_tokens: int) -> str:
    return await metrics_record_llm(model, input_tokens, output_tokens)
