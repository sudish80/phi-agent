import json
import logging
from dataclasses import dataclass, field, asdict
from threading import Lock
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str = ""
    parameters: dict = field(default_factory=dict)
    handler: Optional[Callable] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Tool name is required")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._lock = Lock()

    def register(self, tool: ToolDefinition, overwrite: bool = False):
        if not isinstance(tool, ToolDefinition):
            raise TypeError("Expected a ToolDefinition instance")
        with self._lock:
            if tool.name in self._tools and not overwrite:
                raise ValueError(f"Tool '{tool.name}' is already registered. Use overwrite=True to replace.")
            self._tools[tool.name] = tool
            logger.info("Registered tool '%s'", tool.name)

    def unregister(self, name: str) -> bool:
        with self._lock:
            removed = self._tools.pop(name, None)
            if removed:
                logger.info("Unregistered tool '%s'", name)
                return True
            return False

    def get(self, name: str) -> Optional[ToolDefinition]:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        with self._lock:
            return list(self._tools.values())

    def list_tool_names(self) -> list[str]:
        with self._lock:
            return list(self._tools.keys())

    def execute(self, name: str, **kwargs) -> Any:
        with self._lock:
            tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: '{name}'")
        if tool.handler is None:
            raise ValueError(f"Tool '{name}' has no handler registered")
        return tool.handler(**kwargs)

    def to_openai_tools(self) -> list[dict]:
        with self._lock:
            return [t.to_openai_schema() for t in self._tools.values()]

    def to_json(self, indent: int = 2) -> str:
        with self._lock:
            tools_data = [t.to_dict() for t in self._tools.values()]
        return json.dumps(tools_data, indent=indent)


_registry = ToolRegistry()


def create_dynamic_tool(name: str, handler: Callable, params: dict = None, description: str = "") -> ToolDefinition:
    tool = ToolDefinition(
        name=name,
        description=description or f"Dynamic tool: {name}",
        parameters=params or {
            "type": "object",
            "properties": {},
        },
        handler=handler,
    )
    return tool


def register_tool(tool: ToolDefinition, overwrite: bool = False):
    _registry.register(tool, overwrite=overwrite)


def unregister_tool(name: str) -> bool:
    return _registry.unregister(name)


def get_tool(name: str) -> Optional[ToolDefinition]:
    return _registry.get(name)


def list_tools() -> list[ToolDefinition]:
    return _registry.list_tools()


def execute_tool(name: str, **kwargs) -> Any:
    return _registry.execute(name, **kwargs)


def get_tool_registry() -> ToolRegistry:
    return _registry
