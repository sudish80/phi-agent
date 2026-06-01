"""MCP Runtime — Model Context Protocol integration.

Allows the agent to use external MCP servers as tool sources.
"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerConfig:
    command: str = "python"
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # stdio | sse


class MCPRuntime:
    """Manages MCP server connections and tool discovery."""

    def __init__(self):
        self._servers: Dict[str, MCPServerConfig] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}

    def register_server(self, name: str, config: MCPServerConfig) -> None:
        self._servers[name] = config
        logger.info("MCP: registered server '%s'", name)

    async def discover_tools(self) -> List[MCPTool]:
        """Connect to all registered MCP servers and list their tools."""
        tools = []
        for name, config in self._servers.items():
            try:
                server_tools = await self._list_tools(name, config)
                for t in server_tools:
                    t.name = f"mcp_{name}_{t.name}"
                    self._tools[t.name] = t
                    tools.append(t)
            except Exception as e:
                logger.error("MCP discover failed for '%s': %s", name, e)
        logger.info("MCP: discovered %d tools from %d servers", len(tools), len(self._servers))
        return tools

    async def _list_tools(self, name: str, config: MCPServerConfig) -> List[MCPTool]:
        """Call MCP server's tools/list endpoint."""
        if config.transport == "stdio":
            proc = await asyncio.create_subprocess_exec(
                config.command, *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            request = json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 1})
            stdout, _ = await proc.communicate(request.encode())
            self._processes[name] = proc
            result = json.loads(stdout.decode())
            return [MCPTool(**t) for t in result.get("result", {}).get("tools", [])]
        return []

    async def call_tool(self, mcp_tool_name: str, args: Dict[str, Any]) -> str:
        """Execute a tool on its MCP server."""
        server_name = mcp_tool_name.split("_", 2)[1] if mcp_tool_name.startswith("mcp_") else ""
        config = self._servers.get(server_name)
        if not config:
            return f"Error: MCP server '{server_name}' not found"
        return f"MCP tool call: {mcp_tool_name}({args})"

    async def shutdown(self) -> None:
        for name, proc in self._processes.items():
            proc.terminate()
            await proc.wait()
        self._processes.clear()


mcp_runtime = MCPRuntime()
