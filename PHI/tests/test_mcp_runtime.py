import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from backend.mcp.runtime import MCPRuntime, MCPServerConfig, MCPTool, mcp_runtime


@pytest.fixture
def runtime():
    return MCPRuntime()


class TestMCPRuntime:
    def test_register_server(self, runtime):
        config = MCPServerConfig(command="python", args=["-m", "server"])
        runtime.register_server("my_server", config)
        assert "my_server" in runtime._servers

    def test_register_multiple_servers(self, runtime):
        runtime.register_server("a", MCPServerConfig(command="python"))
        runtime.register_server("b", MCPServerConfig(command="node"))
        assert len(runtime._servers) == 2

    @pytest.mark.asyncio
    async def test_discover_tools_from_stdio_server(self, runtime):
        config = MCPServerConfig(command="python", args=["-c", "print('{}')"])
        runtime.register_server("test_server", config)

        mock_tools = [
            {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {}}},
            {"name": "get_time", "description": "Get time", "parameters": {"type": "object", "properties": {}}},
        ]
        response = {"jsonrpc": "2.0", "result": {"tools": mock_tools}}

        with patch.object(runtime, "_list_tools", new=AsyncMock(return_value=[MCPTool(**t) for t in mock_tools])) as mock_list:
            tools = await runtime.discover_tools()
            assert len(tools) == 2
            assert tools[0].name == "mcp_test_server_get_weather"
            assert tools[0].description == "Get weather"
            assert tools[1].name == "mcp_test_server_get_time"
            mock_list.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_discover_tools_empty_when_no_servers(self, runtime):
        tools = await runtime.discover_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_discover_tools_handles_server_error(self, runtime):
        config = MCPServerConfig(command="python")
        runtime.register_server("failing", config)

        with patch.object(runtime, "_list_tools", new=AsyncMock(side_effect=RuntimeError("Connection failed"))):
            tools = await runtime.discover_tools()
            assert tools == []

    @pytest.mark.asyncio
    async def test_list_tools_stdio_calls_subprocess(self, runtime):
        config = MCPServerConfig(command="echo", args=['{"jsonrpc":"2.0","result":{"tools":[{"name":"tool1","description":"desc","parameters":{}}]}}'])

        with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as mock_proc:
            mock_proc_instance = MagicMock()
            mock_proc_instance.communicate = AsyncMock(return_value=(json.dumps({"jsonrpc": "2.0", "result": {"tools": [{"name": "tool1"}]}}).encode(), b""))
            mock_proc.return_value = mock_proc_instance
            tools = await runtime._list_tools("test", config)
            assert len(tools) == 1
            assert tools[0].name == "tool1"

    @pytest.mark.asyncio
    async def test_list_tools_sse_returns_empty(self, runtime):
        config = MCPServerConfig(transport="sse")
        tools = await runtime._list_tools("test", config)
        assert tools == []

    @pytest.mark.asyncio
    async def test_call_tool_returns_result_string(self, runtime):
        config = MCPServerConfig(command="python")
        runtime.register_server("calc", config)
        runtime._tools["mcp_calc_add"] = MCPTool(name="mcp_calc_add")

        result = await runtime.call_tool("mcp_calc_add", {"a": 1, "b": 2})
        assert "mcp_calc_add" in result
        assert "{'a': 1, 'b': 2}" in result

    @pytest.mark.asyncio
    async def test_call_tool_unknown_server(self, runtime):
        result = await runtime.call_tool("mcp_unknown_tool", {})
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_shutdown_terminates_processes(self, runtime):
        mock_proc = MagicMock()
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock()
        runtime._processes["test"] = mock_proc

        await runtime.shutdown()
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_awaited_once()
        assert len(runtime._processes) == 0


class TestMCPServerConfig:
    def test_defaults(self):
        cfg = MCPServerConfig()
        assert cfg.command == "python"
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.transport == "stdio"

    def test_custom_config(self):
        cfg = MCPServerConfig(
            command="node", args=["server.js"],
            env={"KEY": "val"}, transport="sse",
        )
        assert cfg.command == "node"
        assert cfg.transport == "sse"


class TestMCPTool:
    def test_defaults(self):
        tool = MCPTool(name="test_tool")
        assert tool.name == "test_tool"
        assert tool.description == ""
        assert tool.parameters == {}

    def test_full_constructor(self):
        tool = MCPTool(
            name="search",
            description="Search tool",
            parameters={"type": "object", "properties": {}},
        )
        assert tool.name == "search"
        assert tool.parameters["type"] == "object"
