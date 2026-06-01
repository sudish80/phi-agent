"""Plugin SDK — base classes for creating agent plugins."""

from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class PluginManifest:
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    tools: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)


class BasePlugin:
    """Base class for all plugins."""

    manifest: PluginManifest = field(default_factory=PluginManifest)

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    async def on_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Optional[str]:
        return None


class PluginRegistry:
    """Registry of installed plugins."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> None:
        self._plugins[plugin.manifest.name] = plugin

    def get(self, name: str) -> Optional[BasePlugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> List[BasePlugin]:
        return list(self._plugins.values())

    async def load_all(self) -> None:
        for plugin in self._plugins.values():
            await plugin.on_load()

    async def unload_all(self) -> None:
        for plugin in self._plugins.values():
            await plugin.on_unload()


plugin_registry = PluginRegistry()
