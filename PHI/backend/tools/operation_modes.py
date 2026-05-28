"""Operation Modes — switch task context: planning, reading, writing, building, general.

Each mode adjusts focus, tool priority, and response style.
Can be set manually or auto-detected from the user's query.
"""

import json
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

OPERATION_MODES = {
    "general": {
        "name": "General",
        "description": "Default balanced mode for everyday assistance",
        "focus": "general purpose, quick answers, task switching across domains",
        "prompt_extension": "Respond naturally across all domains. Be concise and balanced.",
        "tool_priority": [],
        "style_guide": "Balanced and conversational",
        "verbosity": 0.5,
    },
    "planning": {
        "name": "Planning",
        "description": "Strategic thinking, goal decomposition, and structured planning",
        "focus": "project roadmaps, goal decomposition, timeline creation, risk analysis, milestone tracking",
        "prompt_extension": "Think strategically and long-term. Break down goals into actionable steps with clear milestones. Consider dependencies, resources, timelines, and risks. Use structured formats like milestone plans, decision trees, and Gantt charts. Be thorough, forward-looking, and organized.",
        "tool_priority": ["goal_decomposition", "task_planning", "scheduling_assistant", "search_web", "get_time", "set_reminder"],
        "style_guide": "Structured and strategic with clear milestones",
        "verbosity": 0.7,
    },
    "reading": {
        "name": "Reading",
        "description": "Deep document analysis, research, and comprehension",
        "focus": "document analysis, literature review, fact extraction, source comparison",
        "prompt_extension": "Focus on deep understanding and thorough analysis. Read carefully, extract key points, facts, and quotes. Compare multiple sources, identify themes, and note contradictions. Be meticulous, cite sources, and provide detailed summaries. Prioritize accuracy over speed.",
        "tool_priority": ["read_file", "search_web", "fact_check", "scrape_web", "summarize_memory", "recall"],
        "style_guide": "Analytical and detail-oriented with citations",
        "verbosity": 0.8,
    },
    "writing": {
        "name": "Writing",
        "description": "Content creation, editing, and formatting assistance",
        "focus": "drafting, editing, proofreading, formatting, creative writing, documentation",
        "prompt_extension": "Focus on clear, effective, and polished writing. Consider audience, tone, structure, and flow. Proofread for grammar, spelling, and style. Use proper markdown formatting. Offer multiple versions or drafts when appropriate. Be creative with language while maintaining clarity and purpose.",
        "tool_priority": ["write_file", "read_file", "search_web", "visualize_data", "debug_code"],
        "style_guide": "Polished and audience-aware with proper formatting",
        "verbosity": 0.7,
    },
    "building": {
        "name": "Building",
        "description": "Active development, coding, and hands-on implementation",
        "focus": "software development, debugging, testing, architecture, deployment",
        "prompt_extension": "Focus on practical implementation. Write clean, working, well-tested code. Consider architecture, edge cases, performance, and security. Be hands-on and solution-oriented. Use development tools freely. Think step by step through implementation. Test your assumptions. Prefer working solutions over theoretical discussions.",
        "tool_priority": ["execute_code", "debug_code", "explain_code", "auto_complete_project", "build_fullstack_app", "coding_agent", "write_file", "read_file", "search_web"],
        "style_guide": "Hands-on and implementation-focused with clean code",
        "verbosity": 0.6,
    },
}

_active_mode = "general"
_auto_detect_enabled = True

_mode_keywords = {
    "planning": [
        "plan", "strategy", "roadmap", "timeline", "milestone", "goal", "objective",
        "project", "schedule", "prepare for", "organize", "blueprint", "framework",
        "road map", "game plan", "action plan", "long term", "future",
    ],
    "reading": [
        "read", "analyze", "research", "summarize", "study", "review", "examine",
        "comprehend", "understand", "explain this", "what does this mean",
        "break down", "analyze this", "document", "article", "paper", "chapter",
        "compare", "contrast", "synthesize",
    ],
    "writing": [
        "write", "draft", "compose", "edit", "rewrite", "proofread", "author",
        "create content", "blog post", "essay", "letter", "email draft",
        "story", "poem", "article", "documentation", "document", "report",
    ],
    "building": [
        "build", "code", "implement", "develop", "program", "create app",
        "make a", "write code", "debug", "fix bug", "refactor", "test",
        "deploy", "scaffold", "generate", "fullstack", "frontend", "backend",
        "api", "database", "function", "class", "module",
    ],
}


def get_active() -> str:
    return _active_mode


def is_auto_detect_enabled() -> bool:
    return _auto_detect_enabled


async def set_mode(mode: str) -> str:
    global _active_mode
    mode = mode.lower().strip()
    if mode not in OPERATION_MODES:
        available = ", ".join(sorted(OPERATION_MODES.keys()))
        return f"Unknown mode '{mode}'. Available: {available}"
    _active_mode = mode
    profile = OPERATION_MODES[mode]
    logger.info(f"Operation mode set to: {mode} ({profile['name']})")
    return f"Switched to **{profile['name']}** mode: {profile['description']}"


async def get_mode() -> str:
    profile = OPERATION_MODES[_active_mode]
    return json.dumps({
        "active_mode": _active_mode,
        "name": profile["name"],
        "description": profile["description"],
        "focus": profile["focus"],
        "style_guide": profile["style_guide"],
        "auto_detect": _auto_detect_enabled,
    }, indent=2)


async def list_modes() -> str:
    return json.dumps({
        name: {
            "name": m["name"],
            "description": m["description"],
            "focus": m["focus"],
        } for name, m in OPERATION_MODES.items()
    }, indent=2)


async def toggle_auto_detect(enabled: Optional[bool] = None) -> str:
    global _auto_detect_enabled
    if enabled is not None:
        _auto_detect_enabled = enabled
    else:
        _auto_detect_enabled = not _auto_detect_enabled
    return f"Auto-detect mode: {'ON' if _auto_detect_enabled else 'OFF'}"


def auto_detect(query: str) -> str:
    if not _auto_detect_enabled:
        return _active_mode
    query_lower = query.lower().strip()
    if not query_lower:
        return "general"
    scores = {}
    for mode, keywords in _mode_keywords.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[mode] = score
    if not scores:
        return "general"
    best = max(scores, key=scores.get)
    if best == _active_mode:
        return _active_mode
    return best


def get_mode_prompt_extension(user_name: str) -> str:
    profile = OPERATION_MODES.get(_active_mode, OPERATION_MODES["general"])
    priority_tools = profile.get("tool_priority", [])
    priority_str = ""
    if priority_tools:
        priority_str = f"\nPreferred tools for this mode: {', '.join(priority_tools[:8])}"
    return f"""
CURRENT OPERATION MODE: {profile['name']}
Focus: {profile['focus']}
Style: {profile['style_guide']}{priority_str}

Mode Instructions:
{profile['prompt_extension']}

Adapt your responses to this mode's focus naturally. Do not announce your mode unless asked.
"""
