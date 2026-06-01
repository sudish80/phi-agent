"""Prompt loader — reads workspace AGENTS.md/SOUL.md/TOOLS.md + skills, assembles system prompt.

Mirrors the openclaw approach: minimal programmatic prompt, rich context from workspace files.
"""

import os
import logging
from functools import lru_cache
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@lru_cache()
def _workspace_dir() -> str:
    """Resolve workspace root from settings, with lazy import to avoid circular deps."""
    from backend.shared.config import settings
    return settings.workspace_dir


def _read_or_none(path: str) -> Optional[str]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Workspace prompt files
# ---------------------------------------------------------------------------

def load_agents_md() -> Optional[str]:
    return _read_or_none(os.path.join(_workspace_dir(), 'AGENTS.md'))


def load_soul_md() -> Optional[str]:
    return _read_or_none(os.path.join(_workspace_dir(), 'SOUL.md'))


def load_tools_md() -> Optional[str]:
    return _read_or_none(os.path.join(_workspace_dir(), 'TOOLS.md'))


# ---------------------------------------------------------------------------
# Skills discovery
# ---------------------------------------------------------------------------

def discover_skills() -> List[Dict[str, str]]:
    """Scan workspace/skills/*/SKILL.md and return [{name, content}]."""
    skills_dir = os.path.join(_workspace_dir(), 'skills')
    if not os.path.isdir(skills_dir):
        return []

    found = []
    for entry in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, entry, 'SKILL.md')
        if os.path.isfile(skill_path):
            content = _read_or_none(skill_path)
            if content:
                found.append({"name": entry, "content": content})
    return found


def load_skill(name: str) -> Optional[str]:
    """Load a single skill by name."""
    path = os.path.join(_workspace_dir(), 'skills', name, 'SKILL.md')
    return _read_or_none(path)


# ---------------------------------------------------------------------------
# System prompt assembly
# ---------------------------------------------------------------------------

def build_system_prompt(
    agent_name: str,
    user_name: str,
    tool_count: int,
    emotion: str = "neutral",
    active_skills: Optional[List[str]] = None,
) -> str:
    """Assemble the full system prompt programmatically (like openclaw).

    Order:
      1. Identity + agent rules (AGENTS.md)
      2. Personality (SOUL.md)
      3. Active skill content
      4. Runtime context (emotion, tool count)
    """
    parts = []

    # 1. Identity
    parts.append(f"You are {agent_name}, an autonomous AI assistant created by {user_name}.")

    # 2. AGENTS.md (behavior rules)
    agents = load_agents_md()
    if agents:
        parts.append(agents)

    # 3. SOUL.md (personality)
    soul = load_soul_md()
    if soul:
        parts.append(soul)

    # 4. Active skills
    if active_skills:
        all_skills = {s["name"]: s["content"] for s in discover_skills()}
        for name in active_skills:
            content = all_skills.get(name)
            if content:
                parts.append(f"## {name}\n{content}")

    # 5. Runtime context (compact)
    parts.append(f"[{tool_count} tools | emotion: {emotion}]")

    return "\n\n".join(parts)
