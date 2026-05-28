"""Context Optimizer — Smart prompt compression, history trimming, and tool catalog optimization.

Reduces token usage by:
- Grouping tools by category with compressed descriptions
- Only including relevant tool categories based on intent + query keywords
- Smart history trimming (summarize old, keep recent verbatim)
- Reusing compressed prompt patterns via cache
"""

import json
import re
import logging
import hashlib
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Category-level grouping for tools — compressed descriptions for the system prompt
TOOL_CATEGORY_SUMMARIES = {
    "system": "System & server: mouse/keyboard automation, window management, system settings, accessibility, remote desktop, startup programs, macros, orchestration, server health check",
    "audio": "Audio editing: trim, concatenate, split by silence, effects (EQ/reverb/compression), format conversion, noise reduction, bookmarks, mixing",
    "memory": "Memory & learning: conversational topics, user preferences, emotion detection, persona creation, digital twin style mimicry, communication style reports",
    "finance": "Payments & business: Stripe payments/refunds, Plaid accounts, Jira issues, Linear issues, Google Drive, Dropbox, Notion",
    "communication": "Messaging: Twilio SMS/calls, Slack messages/channels/history, Discord, Telegram",
    "development": "Development: GitHub repos/issues/PRs",
    "entertainment": "Media: Spotify playback state/search, YouTube search/transcripts",
    "ai": "AI & analytics: predictive analytics, swarm agents, collaboration, emotion companion, meeting assistant, cybersecurity alerts, holographic UI, drone control, BCI, OS layer, text translation",
    "utility": "Utilities: define words, translate text, scrape facts, remember/recall preferences, create/delete personas, style reports, PDF enhancement — fix scanned docs, correct skew, boost contrast, combine images into clean PDF, file search/hash/diff/compress, text analysis, regex, JSON/CSV processing, markdown, date/time/unit conversion, cryptography (UUID, password, hash, encrypt), random numbers, color conversion, math, Python code execution, Jinja2 templates — file/search/hash/diff/compress/type_detect, text/analyze/regex/JSON/CSV/markdown/dates/timezones/units, crypto/UUID/password/hash/encrypt/decrypt, net/ping/DNS/whois/geoip, misc/random/color/math/yesno, sandboxed Python, Jinja2 templates, system info/disk usage, webhook/register/trigger/list/delete — 531+ tools across all categories",
    "search": "Web search & discovery: Tavily AI search, Firecrawl scraping, stock prices",
    "storage": "Cloud storage: Google Drive, Dropbox file listing",
    "automation": "Automation: Zapier webhook triggers, webhook register/trigger/list/delete",
    "health": "Health: Fitbit step tracking, server health check",
    "creative": "Creative: RunwayML video generation, holographic UI render",
    "web": "Web scraping: page scraping with JS rendering, DuckDuckGo search, news, stock, weather, Wikipedia, recipes, products, social mentions, jobs, movies, lyrics, dictionaries, translation, unified search, question answering, ping, DNS, whois, geo IP lookup",
    "productivity": "Productivity: Notion pages, Jira/Linear issues, meeting assistant with notes/actions/summaries",
    "fun": "Fun: desktop pet interaction, facts, jokes, random yes/no answers",
    "security": "Security: JWT auth, refresh tokens, token blacklist, user management, role-based access, input sanitization, audit logging",
    "monitoring": "Monitoring: metrics time-series, LLM cost tracking, tool call tracking, alert engine with thresholds, Prometheus endpoint, performance tracing",
    "qol": "Quality of life: follow-up suggestions, personalization, response caching, tool analytics, conversation tagging, daily briefing, focus mode, emergency stop, DB migrations, memory backup/restore, data export, temp cleanup, language detection, audio mixing",
    "pdf": "PDF processing: enhance scanned PDFs and images — skew correction, border crop, contrast improvement, image-to-PDF conversion",
}


def get_relevant_categories(query: str, intent: str = "") -> List[str]:
    """Determine which tool categories are relevant based on query + intent."""
    q = query.lower()
    categories = set()

    # Intent-based
    intent_cat_map = {
        "greeting": [],
        "time_query": [],
        "weather_query": ["web"],
        "search_query": ["web", "search"],
        "email_task": ["communication"],
        "joke_request": ["fun"],
        "code_task": ["system"],
        "stock_query": ["web"],
        "music_task": ["entertainment", "audio"],
        "news_query": ["web", "search"],
        "memory_task": ["memory"],
        "planning_task": ["productivity", "memory"],
        "analysis_task": ["ai"],
        "security_task": ["security", "monitoring"],
        "automation_task": ["automation", "communication"],
        "creative_task": ["creative"],
        "finance_task": ["finance"],
    }
    categories.update(intent_cat_map.get(intent, []))
    categories.update(get_priority_categories(intent))

    # Keyword-based
    keyword_map = {
        "system": ["mouse", "keyboard", "click", "scroll", "window", "screen", "screenshot",
                     "volume", "brightness", "shutdown", "lock", "startup", "peripheral",
                     "accessibility", "remote", "macro", "shortcut", "monitor", "cpu", "memory",
                     "process", "task"],
        "web": ["search", "find", "look up", "google", "wikipedia", "news", "weather",
                 "stock", "price", "recipe", "lyrics", "movie", "define", "translate",
                 "scrape", "website", "information", "tell me about", "what is", "who is",
                 "research", "browse", "url", "link"],
        "memory": ["remember", "recall", "preference", "personality", "persona", "style",
                    "emotion", "mood", "topic", "digital twin", "mimic", "user", "profile"],
        "audio": ["audio", "sound", "music", "trim", "convert", "noise", "volume",
                   "play", "record", "bookmark", "merge", "effect", "voice", "speech"],
        "communication": ["send", "message", "slack", "discord", "telegram", "twilio",
                           "sms", "call", "email", "notify"],
        "development": ["github", "repo", "repository", "issue", "pr", "pull request",
                         "code", "commit", "push", "branch", "deploy"],
        "ai": ["swarm", "agent", "predict", "drone", "bci", "hologram", "holographic",
                "cyber", "translate", "pet", "analyze"],
        "finance": ["stripe", "payment", "refund", "jira", "linear", "notion",
                     "money", "invoice", "receipt"],
        "storage": ["drive", "dropbox", "file", "upload", "download", "backup"],
        "security": ["auth", "login", "token", "jwt", "password", "permission", "audit",
                      "user", "role", "sanitize", "encrypt", "hash"],
        "monitoring": ["metric", "alert", "monitor", "prometheus", "trace", "cost",
                        "performance", "dashboard", "log"],
        "qol": ["backup", "export", "focus", "briefing", "cache", "migration",
                 "cleanup", "analytics", "tag", "briefing"],
        "fun": ["joke", "fun", "fact", "trivia", "coin", "dice", "card", "game",
                 "pet", "entertain"],
        "entertainment": ["spotify", "youtube", "video", "playlist", "stream", "watch"],
        "creative": ["generate", "create", "design", "render", "draw", "art"],
        "automation": ["zapier", "webhook", "trigger", "automate", "workflow",
                        "pipeline", "task"],
        "productivity": ["calendar", "schedule", "meeting", "note", "reminder",
                          "todo", "task", "plan", "organize"],
        "health": ["fitbit", "step", "health", "exercise", "heart", "sleep"],
        "pdf": ["pdf", "document", "scan", "ocr", "enhance"],
        "utility": ["convert", "format", "transform", "extract", "parse",
                     "validate", "prettify", "minify", "slugify"],
    }

    for cat, keywords in keyword_map.items():
        if any(kw in q for kw in keywords):
            categories.add(cat)

    # Always include essential categories
    essential = {"memory"}  # personality/memory is always relevant
    categories.update(essential)

    # Expand via co-occurrence & dependencies
    categories = set(expand_categories(list(categories)))

    return list(categories)


def compress_tool_list(tools: List[Any], categories: List[str]) -> str:
    """Generate a compressed tool description grouped by categories."""
    parts = []
    included = set(categories)

    for cat in sorted(included):
        summary = TOOL_CATEGORY_SUMMARIES.get(cat)
        if not summary:
            continue
        cat_tools = []
        for t in tools:
            t_cat = t.category if hasattr(t, "category") else t.get("category", "")
            if t_cat == cat:
                cat_tools.append(t.name if hasattr(t, "name") else t.get("name", ""))
        if cat_tools:
            names = sorted(cat_tools)
            parts.append(f"[{cat.upper()}] {summary}")
            parts.append(f"   Tools: {', '.join(names)}")

    if not parts:
        return "No tools available."

    return "\n".join(parts)


def compress_history(history: List[Dict], max_tokens: int = 2000,
                     keep_recent: int = 4) -> List[Dict]:
    """Compress conversation history: summarize old turns, keep recent verbatim."""
    if len(history) <= keep_recent:
        return history

    recent = history[-keep_recent:]
    older = history[:-keep_recent]

    # Summarize older messages
    summary_parts = []
    total_chars = 0
    for msg in older:
        content = msg.get("content", "")
        role = msg.get("role", "user")
        label = "User" if role == "user" else "Assistant"
        snippet = content[:150] if len(content) > 150 else content
        summary_parts.append(f"[{label}]: {snippet}")
        total_chars += len(snippet)

    summary_text = " | ".join(summary_parts)
    if len(summary_text) > 1000:
        summary_text = summary_text[:1000] + "..."

    compressed = [{"role": "system",
                    "content": f"Earlier conversation summary: {summary_text}"}]
    compressed.extend(recent)

    return compressed


def estimate_tokens(text: str) -> int:
    """Rough token estimation (~4 chars per token for English)."""
    return len(text) // 4


def get_compressed_system_prompt(tools: List[Any], query: str, intent: str = "",
                                  user_name: str = "User",
                                  current_time: str = "",
                                  memory_context: str = "No recent memories.",
                                  op_mode_ext: str = "",
                                  personality_ext: str = "") -> str:
    """Build an optimized system prompt with only relevant tools listed."""
    categories = get_relevant_categories(query, intent)
    tool_section = compress_tool_list(tools, categories)

    prompt = f"""You are J.A.R.V.I.S., an AI assistant for {user_name}.

Current time: {current_time}

CAPABILITIES:
{tool_section}

Memory: {memory_context}
{op_mode_ext}{personality_ext}
"""
    return prompt


class PromptCache:
    """Cache for compressed prompts to avoid recomputation."""

    def __init__(self, max_entries: int = 50, ttl: int = 300):
        self._cache: Dict[str, dict] = {}
        self._max = max_entries
        self._ttl = ttl

    def _key(self, query: str, intent: str, categories: str) -> str:
        raw = f"{query}:{intent}:{categories}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, query: str, intent: str, categories: List[str]) -> Optional[str]:
        key = self._key(query, intent, ",".join(sorted(categories)))
        entry = self._cache.get(key)
        if entry and (time.time() - entry["ts"]) < self._ttl:
            return entry["prompt"]
        return None

    def set(self, query: str, intent: str, categories: List[str], prompt: str):
        key = self._key(query, intent, ",".join(sorted(categories)))
        if len(self._cache) >= self._max:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k]["ts"])
            del self._cache[oldest]
        self._cache[key] = {"prompt": prompt, "ts": time.time()}


prompt_cache = PromptCache()


async def optimize_prompt(tools: List[Any], query: str, intent: str = "",
                           user_name: str = "", current_time: str = "",
                           memory_context: str = "",
                           op_mode_ext: str = "", personality_ext: str = "") -> str:
    """Main entry point: returns optimized system prompt."""
    categories = get_relevant_categories(query, intent)
    cached = prompt_cache.get(query, intent, categories)
    if cached:
        return cached
    prompt = get_compressed_system_prompt(tools, query, intent, user_name,
                                           current_time, memory_context,
                                           op_mode_ext, personality_ext)
    prompt_cache.set(query, intent, categories, prompt)
    return prompt


# ---------------------------------------------------------------------------
# Tool switching & routing analysis
# ---------------------------------------------------------------------------

CATEGORY_CO_OCCURRENCE = {
    "web": ["utility", "search", "ai"],
    "search": ["web", "utility"],
    "memory": ["utility", "ai"],
    "utility": ["memory", "web", "system"],
    "system": ["utility", "monitoring", "security"],
    "audio": ["utility", "fun"],
    "communication": ["utility", "automation"],
    "finance": ["utility"],
    "development": ["system", "utility"],
    "ai": ["memory", "utility", "search"],
    "security": ["system", "monitoring"],
    "monitoring": ["system", "security"],
    "qol": ["utility", "memory", "system"],
    "fun": ["utility", "audio"],
    "automation": ["communication", "utility"],
    "productivity": ["utility", "memory"],
    "creative": ["ai", "utility"],
    "entertainment": ["audio", "fun"],
}

CATEGORY_DEPENDENCIES = {
    "search": ["web"],
    "storage": ["web"],
    "development": ["system", "security"],
    "communication": ["automation"],
    "productivity": ["memory"],
}

INTENT_CATEGORY_PRIORITY = {
    "greeting": ["memory"],
    "time_query": ["utility"],
    "weather_query": ["web", "utility"],
    "search_query": ["web", "search", "utility"],
    "email_task": ["communication", "utility"],
    "joke_request": ["fun", "utility"],
    "code_task": ["system", "development", "utility"],
    "stock_query": ["web", "finance", "utility"],
    "music_task": ["entertainment", "audio", "utility"],
    "news_query": ["web", "search"],
    "memory_task": ["memory", "utility"],
    "planning_task": ["productivity", "memory", "utility"],
    "analysis_task": ["ai", "utility", "web"],
    "security_task": ["security", "monitoring", "system"],
    "automation_task": ["automation", "communication", "utility"],
    "creative_task": ["creative", "ai", "utility"],
    "finance_task": ["finance", "web", "utility"],
}


def expand_categories(categories: List[str]) -> List[str]:
    expanded = set(categories)
    for cat in categories:
        expanded.update(CATEGORY_CO_OCCURRENCE.get(cat, []))
    for cat in categories:
        expanded.update(CATEGORY_DEPENDENCIES.get(cat, []))
    return list(expanded)


def get_priority_categories(intent: str) -> List[str]:
    return INTENT_CATEGORY_PRIORITY.get(intent, [])


def analyze_tool_conflicts(query: str, intent: str) -> Dict[str, Any]:
    q = query.lower()
    keywords_found = []
    for cat, kws in keyword_map.items():
        for kw in kws:
            if kw in q:
                keywords_found.append({"category": cat, "keyword": kw})
    categories = get_relevant_categories(query, intent)
    intent_cats = get_priority_categories(intent)
    expanded = expand_categories(categories)
    return {
        "categories_matched": categories,
        "intent_priority_categories": intent_cats,
        "expanded_categories": expanded,
        "keywords_found": keywords_found[:10],
        "suggestion": " or ".join(expanded[:5]) if expanded else "utility",
    }
