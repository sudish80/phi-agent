"""Quality of Life features — follow-up questions, personalization, smart defaults, tool analytics,
abbreviation expansion, response caching, conversation tagging, daily briefing, focus mode, emergency stop.

Also includes Database migration, memory backup/restore, data export, and temp file cleanup.
"""

import json
import os
import logging
import time
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

TOOL_ANALYTICS: Dict[str, int] = {}
RESPONSE_CACHE: Dict[str, dict] = {}
MAX_CACHE_SIZE = 200
TEMP_FILES: List[str] = []
CONVERSATION_TAGS: Dict[str, List[str]] = {}


# --- Suggested Follow-up Questions ---

_FOLLOW_UP_TEMPLATES = {
    "general": [
        "Would you like me to elaborate on any part of that?",
        "Is there anything else I can help with?",
        "Should I save this to your memory for later?",
    ],
    "code": [
        "Want me to explain how this code works?",
        "Should I add error handling to this?",
        "Would you like me to write tests for this?",
    ],
    "research": [
        "Should I search for more sources on this topic?",
        "Want me to summarize the key findings?",
        "Would you like me to save this research to memory?",
    ],
    "planning": [
        "Should I create a timeline for this plan?",
        "Want me to break this into smaller tasks?",
        "Would you like milestone reminders?",
    ],
}

async def suggest_followups(context: str = "general") -> str:
    questions = _FOLLOW_UP_TEMPLATES.get(context, _FOLLOW_UP_TEMPLATES["general"])
    return json.dumps({"context": context, "suggestions": questions}, indent=2)


# --- Personalization ---

_USER_PROFILES: Dict[str, Dict] = {}

async def personalization_get(username: str) -> str:
    profile = _USER_PROFILES.get(username, {})
    return json.dumps(profile, indent=2) if profile else json.dumps({"username": username, "status": "no preferences yet"})


async def personalization_set(username: str, preferences: str) -> str:
    try:
        prefs = json.loads(preferences) if isinstance(preferences, str) else preferences
        _USER_PROFILES[username] = prefs
        return json.dumps({"username": username, "preferences": prefs, "status": "saved"})
    except Exception as e:
        return f"Failed to set preferences: {e}"


async def personalization_adapt(query: str, username: str = "") -> str:
    profile = _USER_PROFILES.get(username, {})
    style = profile.get("response_style", "balanced")
    verbosity = profile.get("verbosity", "medium")
    return json.dumps({
        "adapted": True,
        "style": style,
        "verbosity": verbosity,
        "query": query[:100],
        "suggestion": f"Responding in {style} style at {verbosity} verbosity"
    })


# --- Response Caching ---

async def cache_get(key: str) -> str:
    entry = RESPONSE_CACHE.get(key)
    if not entry:
        return json.dumps({"cached": False, "key": key})
    return json.dumps({"cached": True, "key": key, "response": entry["response"][:200], "age_seconds": round(time.time() - entry["timestamp"])})


async def cache_set(key: str, response: str) -> str:
    if len(RESPONSE_CACHE) >= MAX_CACHE_SIZE:
        oldest = min(RESPONSE_CACHE.keys(), key=lambda k: RESPONSE_CACHE[k]["timestamp"])
        del RESPONSE_CACHE[oldest]
    RESPONSE_CACHE[key] = {"response": response, "timestamp": time.time()}
    return json.dumps({"cached": True, "key": key, "cache_size": len(RESPONSE_CACHE)})


async def cache_clear() -> str:
    count = len(RESPONSE_CACHE)
    RESPONSE_CACHE.clear()
    return f"Cleared {count} cached responses"


async def cache_stats() -> str:
    return json.dumps({"entries": len(RESPONSE_CACHE), "max_size": MAX_CACHE_SIZE}, indent=2)


# --- Tool Usage Analytics ---

async def tool_analytics_track(tool_name: str) -> str:
    TOOL_ANALYTICS[tool_name] = TOOL_ANALYTICS.get(tool_name, 0) + 1
    return json.dumps({"tool": tool_name, "calls": TOOL_ANALYTICS[tool_name]})


async def tool_analytics_report() -> str:
    sorted_tools = sorted(TOOL_ANALYTICS.items(), key=lambda x: x[1], reverse=True)
    total = sum(TOOL_ANALYTICS.values())
    return json.dumps({
        "total_tool_calls": total,
        "unique_tools_used": len(TOOL_ANALYTICS),
        "top_tools": [{"name": name, "calls": count, "pct": round(count / total * 100, 1) if total else 0} for name, count in sorted_tools[:15]],
    }, indent=2)


# --- Command Abbreviation Expansion ---

_ABBREVIATIONS = {
    "idk": "I don't know",
    "imo": "in my opinion",
    "tbh": "to be honest",
    "afaik": "as far as I know",
    "btw": "by the way",
    "fyi": "for your information",
    "lol": "laugh out loud",
    "brb": "be right back",
    "omw": "on my way",
    "np": "no problem",
    "ty": "thank you",
    "yw": "you're welcome",
    "nvm": "never mind",
    "tldr": "too long; didn't read",
    "wip": "work in progress",
}

async def expand_abbreviations(text: str) -> str:
    words = text.split()
    expanded_count = 0
    for i, w in enumerate(words):
        clean = w.strip(".,!?;:")
        if clean.lower() in _ABBREVIATIONS:
            words[i] = words[i].replace(clean, _ABBREVIATIONS[clean.lower()])
            expanded_count += 1
    return json.dumps({"original": text[:200], "expanded": " ".join(words)[:200], "expansions": expanded_count}, indent=2)


# --- Conversation Tagging ---

async def tag_conversation(session_id: str, tags: str) -> str:
    tag_list = [t.strip() for t in tags.split(",")]
    CONVERSATION_TAGS.setdefault(session_id, [])
    CONVERSATION_TAGS[session_id].extend(t for t in tag_list if t not in CONVERSATION_TAGS[session_id])
    return json.dumps({"session_id": session_id, "tags": CONVERSATION_TAGS[session_id]})


async def search_by_tag(tag: str) -> str:
    results = [sid for sid, tags in CONVERSATION_TAGS.items() if tag.lower() in [t.lower() for t in tags]]
    return json.dumps({"tag": tag, "matching_sessions": results}, indent=2)


# --- Daily Briefing ---

_BRIEFING_TEMPLATES = {
    "morning": "Good morning! Here's your daily briefing:\n- {date}\n- You have {tasks} pending tasks\n- {weather_info}\n- {news_headlines}\n- {reminders}",
    "evening": "Evening summary:\n- Completed {tasks_done} tasks today\n- {key_events}\n- Tomorrow's focus: {tomorrow_focus}",
}

async def daily_briefing(time_of_day: str = "morning", username: str = "User") -> str:
    from datetime import date
    briefing = {
        "date": date.today().isoformat(),
        "time_of_day": time_of_day,
        "greeting": f"Good {'morning' if time_of_day == 'morning' else 'evening'}, {username}!",
        "pending_tasks": 0,
        "weather_note": "Weather check available with get_weather tool",
        "headlines": "Run get_news for today's headlines",
        "reminders": "No reminders set",
        "focus_suggestion": "Consider setting a goal for today using the planning mode",
    }
    return json.dumps(briefing, indent=2)


# --- Focus Mode ---

_focus_mode = False
_focus_blocked_tools: List[str] = []

async def focus_mode_set(enabled: bool, blocked_tools: Optional[str] = None) -> str:
    global _focus_mode, _focus_blocked_tools
    _focus_mode = enabled
    if blocked_tools:
        _focus_blocked_tools = [t.strip() for t in blocked_tools.split(",")]
    if enabled:
        return json.dumps({"focus_mode": True, "blocked_tools": _focus_blocked_tools, "note": "Non-essential tools disabled"})
    _focus_blocked_tools = []
    return json.dumps({"focus_mode": False, "note": "All tools available"})


async def focus_mode_status() -> str:
    return json.dumps({"focus_mode": _focus_mode, "blocked_tools": _focus_blocked_tools})


# --- Emergency Stop / Reset ---

_EMERGENCY_STOP = False

async def emergency_stop() -> str:
    global _EMERGENCY_STOP
    _EMERGENCY_STOP = True
    logger.warning("EMERGENCY STOP ACTIVATED — all non-critical operations halted")
    return json.dumps({"status": "emergency_stop_activated", "action": "All non-critical operations halted. Say 'resume' to continue."})


async def emergency_resume() -> str:
    global _EMERGENCY_STOP
    _EMERGENCY_STOP = False
    logger.info("Emergency stop released — normal operations resumed")
    return json.dumps({"status": "resumed", "action": "Normal operations resumed"})


async def emergency_status() -> str:
    return json.dumps({"emergency_stop": _EMERGENCY_STOP})


# --- Database Migration System ---

_MIGRATIONS: List[Dict] = []
_MIGRATIONS_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "migrations"
_MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

async def migration_create(name: str, sql_up: str, sql_down: str) -> str:
    migration = {
        "id": f"mig_{int(time.time())}",
        "name": name,
        "sql_up": sql_up,
        "sql_down": sql_down,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "applied": False,
    }
    _MIGRATIONS.append(migration)
    path = _MIGRATIONS_DIR / f"{migration['id']}_{name.replace(' ', '_')}.json"
    path.write_text(json.dumps(migration, indent=2), encoding="utf-8")
    return json.dumps({"id": migration["id"], "name": name, "file": str(path)})


async def migration_list() -> str:
    return json.dumps([{"id": m["id"], "name": m["name"], "applied": m["applied"], "created": m["created_at"]} for m in _MIGRATIONS], indent=2)


# --- Memory Backup & Restore ---

async def memory_backup(backup_path: Optional[str] = None) -> str:
    path = backup_path or f"memory_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    try:
        sample = {
            "backup_date": datetime.now(timezone.utc).isoformat(),
            "memory_type": "episodic",
            "entries_count": 0,
            "note": "Full memory backup requires ChromaDB integration. This creates a snapshot placeholder.",
        }
        Path(path).write_text(json.dumps(sample, indent=2), encoding="utf-8")
        return json.dumps({"backup_path": path, "status": "created", "note": "Point to ChromaDB path for full backup"})
    except Exception as e:
        return f"Backup failed: {e}"


async def memory_restore(backup_path: str) -> str:
    try:
        data = json.loads(Path(backup_path).read_text(encoding="utf-8"))
        return json.dumps({"restored_from": backup_path, "status": "ok", "entries": data.get("entries_count", 0)})
    except Exception as e:
        return f"Restore failed: {e}"


# --- Data Export ---

async def data_export(data: str, format: str = "json") -> str:
    path = f"export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{format}"
    try:
        if format == "json":
            parsed = json.loads(data) if isinstance(data, str) else data
            Path(path).write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        elif format in ("csv", "txt"):
            Path(path).write_text(data if isinstance(data, str) else str(data), encoding="utf-8")
        else:
            return f"Unsupported export format: {format}"
        return json.dumps({"exported_to": path, "format": format, "size_bytes": Path(path).stat().st_size})
    except Exception as e:
        return f"Export failed: {e}"


# --- Temp File Cleanup ---

async def temp_cleanup(max_age_hours: int = 24) -> str:
    count = 0
    freed_bytes = 0
    for path_str in TEMP_FILES:
        try:
            p = Path(path_str)
            if p.exists():
                age = time.time() - p.stat().st_mtime
                if age > max_age_hours * 3600:
                    freed_bytes += p.stat().st_size
                    p.unlink()
                    count += 1
        except Exception:
            pass
    remaining = [p for p in TEMP_FILES if Path(p).exists()]
    return json.dumps({"cleaned": count, "freed_bytes": freed_bytes, "remaining_temp_files": len(remaining)})


async def temp_register(path: str) -> str:
    TEMP_FILES.append(path)
    return json.dumps({"registered": path, "total_temp_files": len(TEMP_FILES)})


# --- Multi-language Greeting Detection ---

_GREETINGS = {
    "en": ["hello", "hi", "hey", "good morning", "good evening", "howdy", "greetings"],
    "es": ["hola", "buenos días", "buenas tardes", "buenas noches"],
    "fr": ["bonjour", "salut", "bonsoir"],
    "de": ["hallo", "guten morgen", "guten abend", "servus"],
    "it": ["ciao", "buongiorno", "buonasera"],
    "pt": ["olá", "bom dia", "boa tarde", "boa noite"],
    "ja": ["konnichiwa", "ohayou", "konbanwa"],
    "zh": ["你好", "早上好", "晚上好"],
    "ko": ["annyeong", "annyeonghaseyo"],
    "ru": ["privet", "zdravstvuyte", "dobroye utro"],
}

async def detect_language(text: str) -> str:
    text_lower = text.lower().strip()
    scores = {}
    for lang, words in _GREETINGS.items():
        score = sum(1 for w in words if w in text_lower)
        if score > 0:
            scores[lang] = score
    if not scores:
        return json.dumps({"detected_language": "en", "confidence": 0.5, "note": "Defaulting to English"})
    primary = max(scores, key=scores.get)
    total = sum(scores.values())
    return json.dumps({
        "detected_language": primary,
        "confidence": round(scores[primary] / total, 2),
        "all_scores": scores,
    }, indent=2)


# --- Multi-track Audio Mixing ---

async def audio_mix_tracks(file_paths: List[str], output_path: Optional[str] = None, volumes: Optional[List[float]] = None) -> str:
    try:
        from pydub import AudioSegment
        if not file_paths:
            return "No files provided"
        if volumes and len(volumes) != len(file_paths):
            return "Volumes list must match files list length"
        mixed = None
        for i, fp in enumerate(file_paths):
            seg = AudioSegment.from_file(fp)
            if volumes and i < len(volumes):
                seg = seg.apply_gain(volumes[i] * 10 - 10)
            if mixed is None:
                mixed = seg
            else:
                mixed = mixed.overlay(seg)
        if mixed is None:
            return "No audio to mix"
        out = output_path or f"mixed_{len(file_paths)}tracks.wav"
        mixed.export(out, format="wav")
        return json.dumps({"output": out, "tracks": len(file_paths), "duration_ms": len(mixed)})
    except ImportError:
        return "pydub not installed"
    except Exception as e:
        return f"Mix failed: {e}"
