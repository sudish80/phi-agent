import pytest
from backend.orchestrator.engine.policy.resolver import (
    ToolPolicy,
    TOOL_PROFILES,
    resolve_tool_policy,
    filter_tools_by_policy,
    expand_tool_groups,
    TOOL_GROUPS,
)


class TestToolPolicy:
    def test_is_allowed_deny_overrides_allow(self):
        p = ToolPolicy(allow={"file_read", "file_write"}, deny={"file_read"})
        assert p.is_allowed("file_write") is True
        assert p.is_allowed("file_read") is False

    def test_is_allowed_also_allow(self):
        p = ToolPolicy(also_allow={"custom_tool"})
        assert p.is_allowed("custom_tool") is True

    def test_is_allowed_no_rules_returns_true(self):
        p = ToolPolicy()
        assert p.is_allowed("anything") is True

    def test_is_allowed_full_profile_returns_true(self):
        p = ToolPolicy(profile="full")
        assert p.is_allowed("anything") is True

    def test_is_allowed_allow_set_respected(self):
        p = ToolPolicy(allow={"chat", "reply"})
        assert p.is_allowed("chat") is True
        assert p.is_allowed("file_read") is False

    def test_has_active_rules(self):
        assert ToolPolicy().has_active_rules() is False
        assert ToolPolicy(allow={"x"}).has_active_rules() is True
        assert ToolPolicy(deny={"x"}).has_active_rules() is True
        assert ToolPolicy(profile="full").has_active_rules() is True
        assert ToolPolicy(also_allow={"x"}).has_active_rules() is True


class TestProfiles:
    def test_minimal_profile_has_basic_tools(self):
        assert TOOL_PROFILES["minimal"] == {"chat", "reply", "memory_recall", "memory_save"}

    def test_full_profile_is_empty_set(self):
        assert TOOL_PROFILES["full"] == set()

    def test_general_profile_contains_web_tools(self):
        assert "web_search" in TOOL_PROFILES["general"]
        assert "file_read" in TOOL_PROFILES["general"]

    def test_coding_profile_contains_dev_tools(self):
        assert "run_python" in TOOL_PROFILES["coding"]
        assert "bash_exec" in TOOL_PROFILES["coding"]

    def test_readonly_profile_no_write_tools(self):
        assert "file_write" not in TOOL_PROFILES["readonly"]
        assert "file_read" in TOOL_PROFILES["readonly"]

    def test_all_profiles_defined(self):
        expected = {"minimal", "readonly", "coding", "general", "full"}
        assert set(TOOL_PROFILES.keys()) == expected


class TestResolveToolPolicy:
    def test_merges_multiple_layers(self):
        result = resolve_tool_policy(
            agent_policy=ToolPolicy(allow={"chat"}),
            global_policy=ToolPolicy(allow={"web_search"}),
        )
        assert result.is_allowed("chat") is True
        assert result.is_allowed("web_search") is True

    def test_deny_wins_over_allow(self):
        result = resolve_tool_policy(
            agent_policy=ToolPolicy(allow={"file_read", "file_write"}),
            global_policy=ToolPolicy(deny={"file_write"}),
        )
        assert result.is_allowed("file_read") is True
        assert result.is_allowed("file_write") is False

    def test_profile_expands_in_layer(self):
        result = resolve_tool_policy(
            agent_policy=ToolPolicy(profile="minimal"),
        )
        assert result.is_allowed("chat") is True
        assert result.is_allowed("file_read") is False

    def test_subagent_layer_takes_priority(self):
        result = resolve_tool_policy(
            subagent_policy=ToolPolicy(allow={"secret_tool"}),
            global_policy=ToolPolicy(allow={}),
        )
        assert result.is_allowed("secret_tool") is True

    def test_all_none_returns_empty_policy(self):
        result = resolve_tool_policy()
        assert result.is_allowed("anything") is True

    def test_also_allow_merged(self):
        result = resolve_tool_policy(
            agent_policy=ToolPolicy(also_allow={"special_tool"}),
        )
        assert result.is_allowed("special_tool") is True


class TestFilterToolsByPolicy:
    def test_filters_correctly(self, sample_tools):
        policy = ToolPolicy(allow={"chat", "web_search", "memory_save"})
        filtered = filter_tools_by_policy(sample_tools, policy)
        names = [t["name"] for t in filtered]
        assert names == ["web_search", "chat", "memory_save"]

    def test_returns_all_when_no_rules(self, sample_tools):
        policy = ToolPolicy()
        filtered = filter_tools_by_policy(sample_tools, policy)
        assert len(filtered) == len(sample_tools)

    def test_returns_empty_when_none_allowed(self, sample_tools):
        policy = ToolPolicy(allow={"nonexistent"})
        filtered = filter_tools_by_policy(sample_tools, policy)
        assert filtered == []

    def test_deny_removes_from_results(self, sample_tools):
        policy = ToolPolicy(deny={"file_read", "file_write"})
        filtered = filter_tools_by_policy(sample_tools, policy)
        names = [t["name"] for t in filtered]
        assert "file_read" not in names
        assert "chat" in names


class TestExpandToolGroups:
    def test_expands_group_references(self):
        expanded = expand_tool_groups({"group:files", "chat"})
        assert "file_read" in expanded
        assert "file_write" in expanded
        assert "chat" in expanded

    def test_unknown_group_returns_empty(self):
        expanded = expand_tool_groups({"group:nonexistent"})
        assert expanded == set()

    def test_non_group_items_preserved(self):
        expanded = expand_tool_groups({"chat", "reply"})
        assert expanded == {"chat", "reply"}

    def test_all_tool_groups_defined(self):
        expected = {"files", "web", "system", "communication", "ai", "memory", "credentials"}
        assert set(TOOL_GROUPS.keys()) == expected
