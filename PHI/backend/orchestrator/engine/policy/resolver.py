"""Tool Policy Engine — layered allow/deny, profiles, group scoping.

Mirrors openclaw's agent-tools.policy.ts architecture:
  agent-level > provider-level > global > group > sandbox > subagent > inherited
"""

from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field


@dataclass
class ToolPolicy:
    allow: Set[str] = field(default_factory=set)
    deny: Set[str] = field(default_factory=set)
    also_allow: Set[str] = field(default_factory=set)
    profile: Optional[str] = None

    def is_allowed(self, tool_name: str) -> bool:
        if tool_name in self.deny:
            return False
        if tool_name in self.allow:
            return True
        if tool_name in self.also_allow:
            return True
        if not self.allow and not self.profile:
            return True
        if self.profile == "full":
            return True
        return False

    def has_active_rules(self) -> bool:
        return bool(self.allow or self.deny or self.profile or self.also_allow)


TOOL_PROFILES: Dict[str, Set[str]] = {
    "minimal": {"chat", "reply", "memory_recall", "memory_save"},
    "readonly": {
        "file_read", "web_search", "scrape_page", "system_info",
        "disk_usage", "memory_recall", "credential_search",
    },
    "coding": {
        "run_python", "file_read", "file_write", "file_search",
        "bash_exec", "git_status", "git_diff", "git_log",
    },
    "general": {
        # Web
        "web_search", "scrape_page", "scrape_search", "open_url", "weather",
        # Files
        "file_read", "file_write", "file_search", "file_type_detect",
        # System
        "system_info", "disk_usage",
        # Memory
        "memory_save", "memory_recall", "memory_search",
        # Communication
        "send_email", "send_slack", "send_discord",
        # Utility
        "generate_image", "generate_qr", "text_to_speech", "unit_convert",
        "date_format", "timezone_convert", "calculate",
        # Credentials
        "credential_save", "credential_get", "credential_search",
    },
    "full": set(),
}


def resolve_tool_policy(
    agent_policy: Optional[ToolPolicy] = None,
    provider_policy: Optional[ToolPolicy] = None,
    global_policy: Optional[ToolPolicy] = None,
    group_policy: Optional[ToolPolicy] = None,
    sandbox_policy: Optional[ToolPolicy] = None,
    subagent_policy: Optional[ToolPolicy] = None,
    inherited_policy: Optional[ToolPolicy] = None,
) -> ToolPolicy:
    """Merge policies from most-specific to least-specific (first match wins)."""
    layers = [
        ("subagent", subagent_policy),
        ("sandbox", sandbox_policy),
        ("group", group_policy),
        ("agent", agent_policy),
        ("provider", provider_policy),
        ("inherited", inherited_policy),
        ("global", global_policy),
    ]

    merged = ToolPolicy()
    for name, layer in layers:
        if layer is None:
            continue
        if layer.profile:
            profile_tools = TOOL_PROFILES.get(layer.profile, set())
            merged.allow.update(profile_tools)
        merged.allow.update(layer.allow)
        merged.deny.update(layer.deny)
        merged.also_allow.update(layer.also_allow)

    return merged


def filter_tools_by_policy(
    tools: List[Dict[str, Any]],
    policy: ToolPolicy,
) -> List[Dict[str, Any]]:
    """Filter a list of tool dicts through a policy."""
    if not policy.has_active_rules():
        return tools
    result = []
    for t in tools:
        name = t.get("name", "")
        if policy.is_allowed(name):
            result.append(t)
    return result


# Predefined tool groups (for bulk allow/deny)
TOOL_GROUPS: Dict[str, Set[str]] = {
    "files": {"file_read", "file_write", "file_search", "file_delete", "file_move", "file_copy"},
    "web": {"web_search", "scrape_page", "scrape_search", "web_screenshot", "open_url"},
    "system": {"system_info", "disk_usage", "process_list", "process_kill", "computer_control"},
    "communication": {"send_email", "send_sms", "send_slack", "send_discord", "webhook_trigger"},
    "ai": {"generate_image", "text_to_speech", "speech_to_text"},
    "memory": {"memory_save", "memory_recall", "memory_search", "memory_delete"},
    "credentials": {"credential_save", "credential_get", "credential_search", "credential_delete"},
}


def expand_tool_groups(allow: Set[str]) -> Set[str]:
    """Expand group names in a set into individual tool names."""
    expanded = set()
    for item in allow:
        if item.startswith("group:"):
            group_name = item[6:]
            expanded.update(TOOL_GROUPS.get(group_name, set()))
        else:
            expanded.add(item)
    return expanded
