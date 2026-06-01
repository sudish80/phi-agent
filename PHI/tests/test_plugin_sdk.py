import pytest
from unittest.mock import AsyncMock
from backend.plugin_sdk.base import (
    BasePlugin,
    PluginManifest,
    PluginRegistry,
    plugin_registry,
)
from backend.plugin_sdk.tool_registry import (
    ToolRegistry,
    ToolDefinition,
    create_dynamic_tool,
    get_tool_registry,
)


class TestPluginRegistry:
    @pytest.fixture
    def registry(self):
        return PluginRegistry()

    def test_register(self, registry):
        plugin = BasePlugin()
        plugin.manifest = PluginManifest(name="test_plugin")
        registry.register(plugin)
        assert registry.get("test_plugin") is plugin

    def test_get_nonexistent(self, registry):
        assert registry.get("nope") is None

    def test_list_plugins(self, registry):
        p1 = BasePlugin()
        p1.manifest = PluginManifest(name="p1")
        p2 = BasePlugin()
        p2.manifest = PluginManifest(name="p2")
        registry.register(p1)
        registry.register(p2)
        plugins = registry.list_plugins()
        assert len(plugins) == 2

    def test_list_plugins_empty(self, registry):
        assert registry.list_plugins() == []

    @pytest.mark.asyncio
    async def test_load_all_calls_on_load(self, registry):
        plugin = BasePlugin()
        plugin.manifest = PluginManifest(name="test")
        plugin.on_load = AsyncMock()
        registry.register(plugin)
        await registry.load_all()
        plugin.on_load.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unload_all_calls_on_unload(self, registry):
        plugin = BasePlugin()
        plugin.manifest = PluginManifest(name="test")
        plugin.on_unload = AsyncMock()
        registry.register(plugin)
        await registry.unload_all()
        plugin.on_unload.assert_awaited_once()

    def test_register_overwrites(self, registry):
        p1 = BasePlugin()
        p1.manifest = PluginManifest(name="over")
        p2 = BasePlugin()
        p2.manifest = PluginManifest(name="over")
        registry.register(p1)
        registry.register(p2)
        assert registry.get("over") is p2


class TestPluginManifest:
    def test_defaults(self):
        m = PluginManifest(name="my_plugin")
        assert m.version == "0.1.0"
        assert m.description == ""
        assert m.author == ""
        assert m.tools == []
        assert m.requires == []

    def test_full_manifest(self):
        m = PluginManifest(
            name="advanced",
            version="1.0.0",
            description="Does stuff",
            author="bot",
            tools=["search", "compute"],
            requires=["numpy"],
        )
        assert m.author == "bot"
        assert m.tools == ["search", "compute"]


class TestBasePlugin:
    @pytest.mark.asyncio
    async def test_on_load_default(self):
        p = BasePlugin()
        p.manifest = PluginManifest(name="test")
        result = await p.on_load()
        assert result is None

    @pytest.mark.asyncio
    async def test_on_unload_default(self):
        p = BasePlugin()
        p.manifest = PluginManifest(name="test")
        result = await p.on_unload()
        assert result is None

    @pytest.mark.asyncio
    async def test_on_tool_call_default(self):
        p = BasePlugin()
        p.manifest = PluginManifest(name="test")
        result = await p.on_tool_call("any", {})
        assert result is None


class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_register(self, registry):
        tool = ToolDefinition(name="search", description="Search tool")
        registry.register(tool)
        assert registry.get("search") is tool

    def test_register_duplicate_raises(self, registry):
        tool = ToolDefinition(name="dup")
        registry.register(tool)
        with pytest.raises(ValueError):
            registry.register(ToolDefinition(name="dup"))

    def test_register_duplicate_with_overwrite(self, registry):
        t1 = ToolDefinition(name="dup", description="first")
        t2 = ToolDefinition(name="dup", description="second")
        registry.register(t1)
        registry.register(t2, overwrite=True)
        assert registry.get("dup").description == "second"

    def test_register_non_tool_raises(self, registry):
        with pytest.raises(TypeError):
            registry.register("not_a_tool")

    def test_unregister(self, registry):
        tool = ToolDefinition(name="temp")
        registry.register(tool)
        assert registry.unregister("temp") is True
        assert registry.get("temp") is None

    def test_unregister_nonexistent(self, registry):
        assert registry.unregister("ghost") is False

    def test_list_tools(self, registry):
        registry.register(ToolDefinition(name="a"))
        registry.register(ToolDefinition(name="b"))
        names = [t.name for t in registry.list_tools()]
        assert sorted(names) == ["a", "b"]

    def test_list_tool_names(self, registry):
        registry.register(ToolDefinition(name="x"))
        registry.register(ToolDefinition(name="y"))
        names = registry.list_tool_names()
        assert "x" in names
        assert "y" in names

    def test_execute_calls_handler(self, registry):
        def handler(greeting):
            return f"{greeting}, world"

        tool = ToolDefinition(name="hello", handler=handler)
        registry.register(tool)
        result = registry.execute("hello", greeting="Hi")
        assert result == "Hi, world"

    def test_execute_unknown_tool_raises(self, registry):
        with pytest.raises(KeyError):
            registry.execute("unknown")

    def test_execute_no_handler_raises(self, registry):
        registry.register(ToolDefinition(name="nohandler"))
        with pytest.raises(ValueError):
            registry.execute("nohandler")

    def test_to_openai_tools(self, registry):
        tool = ToolDefinition(
            name="weather",
            description="Get weather",
            parameters={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        registry.register(tool)
        oai_tools = registry.to_openai_tools()
        assert len(oai_tools) == 1
        assert oai_tools[0]["function"]["name"] == "weather"
        assert oai_tools[0]["type"] == "function"

    def test_to_json(self, registry):
        registry.register(ToolDefinition(name="tool1", description="desc"))
        data = registry.to_json()
        assert '"tool1"' in data
        assert '"desc"' in data

    def test_tool_definition_no_name_raises(self):
        with pytest.raises(ValueError):
            ToolDefinition(name="")


class TestCreateDynamicTool:
    def test_creates_tool_with_handler(self):
        def my_handler(**kwargs):
            return "ok"

        tool = create_dynamic_tool("my_dynamic_tool", my_handler)
        assert tool.name == "my_dynamic_tool"
        assert tool.handler is my_handler
        assert "Dynamic tool" in tool.description

    def test_custom_params_and_description(self):
        def handler(**kw):
            return kw

        tool = create_dynamic_tool(
            "custom",
            handler,
            params={"type": "object", "properties": {"x": {"type": "int"}}},
            description="Custom tool",
        )
        assert tool.description == "Custom tool"
        assert tool.parameters["properties"]["x"]["type"] == "int"

    def test_to_dict(self):
        def handler(**kw):
            return kw

        tool = create_dynamic_tool("dtool", handler)
        d = tool.to_dict()
        assert d["name"] == "dtool"
        assert "parameters" in d

    def test_to_openai_schema(self):
        def handler(**kw):
            return kw

        tool = create_dynamic_tool("dtool", handler)
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "dtool"
